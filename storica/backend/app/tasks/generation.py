"""Generation tasks for Celery."""

import asyncio
import logging
import re
from typing import Any, Optional

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import get_settings
from app.models.cost import CostRecord
from app.models.generation import GenerationTask, TaskStatus
from app.models.project import ContentType, Project, ProjectStage
from app.services.author import AuthorService
from app.services.llm import AsyncLLMClient
from app.services.project import ProjectService
from app.services.project_adapter import DatabaseProjectAdapter
from app.tasks.celery_app import celery_app

from app.services.prompts import PromptTemplates

settings = get_settings()
logger = logging.getLogger(__name__)


def get_async_session() -> async_sessionmaker[AsyncSession]:
    """Create async session for task."""
    # Use sync database URL converted to async
    db_url = settings.database_url
    engine = create_async_engine(db_url, echo=False)
    return async_sessionmaker(engine, expire_on_commit=False)


async def update_task_progress(
    session: AsyncSession,
    task_id: int,
    status: TaskStatus,
    progress: int,
    message: str,
):
    """Update task progress in database."""
    result = await session.execute(
        select(GenerationTask).where(GenerationTask.id == task_id)
    )
    task = result.scalar_one()
    task.status = status
    task.progress_percent = progress
    task.progress_message = message
    await session.commit()

    # Publish to WebSocket (fire and forget)
    try:
        import redis.asyncio as redis
        r = redis.from_url(settings.redis_url)
        import json
        await r.publish(f"project:{task.project_id}", json.dumps({
            "project_id": task.project_id,
            "event_type": "generation.progress",
            "data": {
                "task_id": task_id,
                "status": status.value,
                "message": message,
                "progress_percent": progress,
            }
        }))
        await r.close()
    except Exception:
        pass  # Don't fail if Redis unavailable


async def record_cost(
    session: AsyncSession,
    user_id: int,
    project_id: int,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
):
    """Record LLM usage cost."""
    record = CostRecord(
        user_id=user_id,
        project_id=project_id,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
    )
    session.add(record)
    await session.commit()


async def _run_essence_generation(task_id: int):
    """Generate essence document."""
    AsyncSessionLocal = get_async_session()

    async with AsyncSessionLocal() as session:
        # Get task and project
        result = await session.execute(
            select(GenerationTask).where(GenerationTask.id == task_id)
        )
        task = result.scalar_one()

        result = await session.execute(
            select(Project).where(Project.id == task.project_id)
        )
        project = result.scalar_one()

        await update_task_progress(
            session, task_id, TaskStatus.RUNNING, 10, "Loading author profile..."
        )

        # Get author context
        author_service = AuthorService()
        author_context = author_service.get_prompt_context(project.author_id)

        if not author_context:
            task.status = TaskStatus.FAILED
            task.error_message = f"Author not found: {project.author_id}"
            await session.commit()
            return

        await update_task_progress(
            session, task_id, TaskStatus.RUNNING, 30, "Generating essence..."
        )

        # Generate essence
        llm = AsyncLLMClient(model=settings.model_essence)
        prompt = PromptTemplates.essence(
            seed=project.seed or "A story worth telling",
            author_context=author_context,
            guidance=task.guidance,
        )

        text, input_tokens, output_tokens = await llm.generate(prompt)
        cost = llm.calculate_cost(input_tokens, output_tokens)

        await update_task_progress(
            session, task_id, TaskStatus.RUNNING, 80, "Saving content..."
        )

        # Save essence
        service = ProjectService(session)
        await service.save_content(project.id, ContentType.ESSENCE, text)

        # Record cost
        await record_cost(
            session, project.user_id, project.id,
            llm.model, input_tokens, output_tokens, cost
        )

        # Update task
        task.result = text
        task.status = TaskStatus.AWAITING_APPROVAL
        task.progress_percent = 100
        task.progress_message = "Ready for approval"
        await session.commit()


async def _run_architecture_generation(task_id: int):
    """Generate architecture document."""
    AsyncSessionLocal = get_async_session()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(GenerationTask).where(GenerationTask.id == task_id)
        )
        task = result.scalar_one()

        result = await session.execute(
            select(Project).where(Project.id == task.project_id)
        )
        project = result.scalar_one()

        await update_task_progress(
            session, task_id, TaskStatus.RUNNING, 10, "Loading context..."
        )

        # Get essence
        adapter = DatabaseProjectAdapter(session, project.id)
        essence = await adapter.get_essence()

        if not essence:
            task.status = TaskStatus.FAILED
            task.error_message = "Essence not found. Generate essence first."
            await session.commit()
            return

        # Get author context
        author_service = AuthorService()
        author_context = author_service.get_prompt_context(project.author_id)

        await update_task_progress(
            session, task_id, TaskStatus.RUNNING, 30, "Generating architecture..."
        )

        llm = AsyncLLMClient(model=settings.model_architecture)
        prompt = PromptTemplates.architecture(
            essence=essence,
            author_context=author_context,
            target_words=project.target_words,
            guidance=task.guidance,
        )

        text, input_tokens, output_tokens = await llm.generate(prompt)
        cost = llm.calculate_cost(input_tokens, output_tokens)

        await update_task_progress(
            session, task_id, TaskStatus.RUNNING, 70, "Parsing chapter count..."
        )

        # Parse chapter count from architecture
        chapter_match = re.search(r"(\d+)\s*chapters?", text.lower())
        total_chapters = int(chapter_match.group(1)) if chapter_match else 10

        await update_task_progress(
            session, task_id, TaskStatus.RUNNING, 80, "Saving content..."
        )

        # Save architecture
        service = ProjectService(session)
        await service.save_content(project.id, ContentType.ARCHITECTURE, text)
        await service.update_stage(project.id, ProjectStage.ARCHITECTURE, total_chapters=total_chapters)

        # Record cost
        await record_cost(
            session, project.user_id, project.id,
            llm.model, input_tokens, output_tokens, cost
        )

        task.result = text
        task.status = TaskStatus.AWAITING_APPROVAL
        task.progress_percent = 100
        task.progress_message = f"Ready for approval ({total_chapters} chapters planned)"
        await session.commit()


def _parse_yaml_response(response: str) -> tuple[dict[str, Any], list[str]]:
    """Parse YAML from LLM response with error handling.

    Returns:
        Tuple of (parsed_data, errors)
    """
    errors: list[str] = []
    yaml_content = response

    # Extract YAML from markdown code blocks
    if "```yaml" in response:
        start = response.find("```yaml") + 7
        end = response.find("```", start)
        if end == -1:
            end = len(response)
            errors.append("YAML block not properly closed")
        yaml_content = response[start:end].strip()
    elif "```" in response:
        start = response.find("```") + 3
        end = response.find("```", start)
        if end == -1:
            end = len(response)
        yaml_content = response[start:end].strip()

    try:
        result = yaml.safe_load(yaml_content) or {}
        return result, errors
    except yaml.YAMLError as e:
        error_msg = f"YAML parse error: {str(e)}"
        errors.append(error_msg)
        logger.warning(f"YAML parse failed: {error_msg}")
        return {}, errors


async def _run_prevalidation(
    llm: AsyncLLMClient,
    blueprint: str,
    story_bible: dict[str, Any],
    architecture: str,
) -> tuple[str, dict[str, Any], list[str], int, int, float]:
    """Run pre-validation of blueprint against story bible.

    Returns:
        Tuple of (status, validation_result, warnings, input_tokens, output_tokens, cost)
    """
    prompt = PromptTemplates.prevalidation(
        blueprint=blueprint,
        story_bible=story_bible,
        architecture=architecture,
    )

    response, input_tokens, output_tokens = await llm.generate(prompt)
    cost = llm.calculate_cost(input_tokens, output_tokens)

    # Parse validation response
    result, errors = _parse_yaml_response(response)

    if errors:
        logger.warning(f"Prevalidation parse errors: {errors}")

    status = result.get("validation_status", "warn")
    warnings = []

    # Extract warnings for prose prompt
    for char in result.get("unknown_characters", []):
        warnings.append(f"Unknown character: {char.get('name', 'unknown')}")

    for loc in result.get("unknown_locations", []):
        warnings.append(f"Unknown location: {loc.get('name', 'unknown')}")

    for warning in result.get("continuity_warnings", []):
        severity = warning.get("severity", "low")
        if severity in ["medium", "high"]:
            warnings.append(f"Continuity: {warning.get('issue', 'unknown issue')}")

    return status, result, warnings, input_tokens, output_tokens, cost


async def _run_critique(
    llm: AsyncLLMClient,
    draft: str,
    blueprint: str,
    author_context: str,
    story_bible: dict[str, Any],
) -> tuple[dict[str, Any], bool, int, int, float]:
    """Run self-critique of draft chapter.

    Returns:
        Tuple of (critique_result, needs_revision, input_tokens, output_tokens, cost)
    """
    prompt = PromptTemplates.critique(
        draft=draft,
        blueprint=blueprint,
        author_context=author_context,
        story_bible=story_bible,
    )

    response, input_tokens, output_tokens = await llm.generate(prompt)
    cost = llm.calculate_cost(input_tokens, output_tokens)

    result, errors = _parse_yaml_response(response)

    if errors:
        logger.warning(f"Critique parse errors: {errors}")
        # Default to no revision if we can't parse
        return {"overall_score": 7, "error": errors}, False, input_tokens, output_tokens, cost

    overall_score = result.get("overall_score", 7)
    needs_revision = result.get("needs_revision", overall_score < 7)

    return result, needs_revision, input_tokens, output_tokens, cost


async def _run_polish(
    llm: AsyncLLMClient,
    draft: str,
    critique_result: dict[str, Any],
    author_context: str,
    blueprint: str,
) -> tuple[str, int, int, float]:
    """Run polish/revision based on critique.

    Returns:
        Tuple of (revised_chapter, input_tokens, output_tokens, cost)
    """
    prompt = PromptTemplates.polish(
        draft=draft,
        critique_result=critique_result,
        author_context=author_context,
        blueprint=blueprint,
    )

    revised, input_tokens, output_tokens = await llm.generate(
        prompt, max_tokens=16384
    )
    cost = llm.calculate_cost(input_tokens, output_tokens)

    return revised, input_tokens, output_tokens, cost


async def _run_blueprint_generation(task_id: int):
    """Generate chapter blueprint."""
    AsyncSessionLocal = get_async_session()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(GenerationTask).where(GenerationTask.id == task_id)
        )
        task = result.scalar_one()

        result = await session.execute(
            select(Project).where(Project.id == task.project_id)
        )
        project = result.scalar_one()

        chapter_num = task.chapter_num

        await update_task_progress(
            session, task_id, TaskStatus.RUNNING, 10,
            f"Loading context for chapter {chapter_num}..."
        )

        adapter = DatabaseProjectAdapter(session, project.id)
        architecture = await adapter.get_architecture()

        if not architecture:
            task.status = TaskStatus.FAILED
            task.error_message = "Architecture not found. Generate architecture first."
            await session.commit()
            return

        # Get previous blueprints for continuity
        all_blueprints = await adapter.get_all_blueprints()
        previous_blueprints = {
            k: v for k, v in all_blueprints.items() if k < chapter_num
        }

        author_service = AuthorService()
        author_context = author_service.get_prompt_context(project.author_id)

        await update_task_progress(
            session, task_id, TaskStatus.RUNNING, 30,
            f"Generating blueprint for chapter {chapter_num}..."
        )

        llm = AsyncLLMClient(model=settings.model_blueprint)
        prompt = PromptTemplates.blueprint(
            chapter_num=chapter_num,
            architecture=architecture,
            author_context=author_context,
            previous_blueprints=previous_blueprints,
            guidance=task.guidance,
        )

        text, input_tokens, output_tokens = await llm.generate(prompt)
        cost = llm.calculate_cost(input_tokens, output_tokens)

        await update_task_progress(
            session, task_id, TaskStatus.RUNNING, 80, "Saving blueprint..."
        )

        service = ProjectService(session)
        await service.save_blueprint(project.id, chapter_num, text)

        # Record cost
        await record_cost(
            session, project.user_id, project.id,
            llm.model, input_tokens, output_tokens, cost
        )

        task.result = text
        task.status = TaskStatus.AWAITING_APPROVAL
        task.progress_percent = 100
        task.progress_message = f"Blueprint {chapter_num} ready for approval"
        await session.commit()


async def _run_chapter_generation(task_id: int):
    """Generate chapter prose with pre-validation, critique, and polish pipeline.

    Pipeline phases:
    1. Load context (10%) - Get blueprint, architecture, story bible, previous chapters
    2. Pre-validation (20%) - Check blueprint against story bible
    3. Generate draft (40%) - First draft with gemini-2.0-flash
    4. Critique (55%) - Self-review for consistency and voice
    5. Polish if needed (70%) - Rewrite if critique score < 7
    6. Update story bible (85%) - Extract continuity info
    7. Save (95%) - Save final chapter and record costs
    """
    AsyncSessionLocal = get_async_session()
    total_costs: list[tuple[str, int, int, float]] = []  # (model, in, out, cost)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(GenerationTask).where(GenerationTask.id == task_id)
        )
        task = result.scalar_one()

        result = await session.execute(
            select(Project).where(Project.id == task.project_id)
        )
        project = result.scalar_one()

        chapter_num = task.chapter_num

        # ============================================================
        # Phase 1: Load context (10%)
        # ============================================================
        await update_task_progress(
            session, task_id, TaskStatus.RUNNING, 10,
            f"Loading context for chapter {chapter_num}..."
        )

        adapter = DatabaseProjectAdapter(session, project.id)

        # Get blueprint for this chapter
        blueprint = await adapter.get_blueprint(chapter_num)
        if not blueprint:
            task.status = TaskStatus.FAILED
            task.error_message = f"Blueprint for chapter {chapter_num} not found."
            await session.commit()
            return

        # Get architecture for pre-validation
        architecture = await adapter.get_architecture() or ""

        # Get story bible (parse as dict if JSON/YAML, else use as context)
        story_bible_raw = await adapter.get_story_bible() or ""
        story_bible: dict[str, Any] = {}
        if story_bible_raw:
            try:
                story_bible = yaml.safe_load(story_bible_raw) or {}
            except yaml.YAMLError:
                # If not valid YAML, treat as empty dict but keep raw for context
                story_bible = {}

        # Get more previous chapters for better context (5 instead of 2)
        previous_chapters_list = await adapter.get_previous_chapters(
            chapter_num, limit=settings.context_previous_chapters
        )
        # Convert to dict format expected by prompts
        previous_chapters: dict[int, str] = {}
        for i, content in enumerate(previous_chapters_list):
            prev_num = chapter_num - len(previous_chapters_list) + i
            previous_chapters[prev_num] = content

        author_service = AuthorService()
        author_context = author_service.get_prompt_context(project.author_id)

        if not author_context:
            task.status = TaskStatus.FAILED
            task.error_message = f"Author not found: {project.author_id}"
            await session.commit()
            return

        # ============================================================
        # Phase 2: Pre-validation (20%)
        # ============================================================
        await update_task_progress(
            session, task_id, TaskStatus.RUNNING, 20,
            f"Pre-validating blueprint for chapter {chapter_num}..."
        )

        validation_warnings: list[str] = []
        try:
            prevalidation_llm = AsyncLLMClient(model=settings.model_prevalidation)
            (
                validation_status,
                validation_result,
                validation_warnings,
                pv_in,
                pv_out,
                pv_cost,
            ) = await _run_prevalidation(
                prevalidation_llm, blueprint, story_bible, architecture
            )
            total_costs.append((settings.model_prevalidation, pv_in, pv_out, pv_cost))

            if validation_status == "fail":
                # Log but don't fail - continue with warnings
                logger.warning(
                    f"Chapter {chapter_num} pre-validation failed: {validation_warnings}"
                )

            # Auto-add recommended characters/locations to story bible
            recommended = validation_result.get("recommended_bible_additions", {})
            if recommended.get("characters"):
                if "characters" not in story_bible:
                    story_bible["characters"] = {}
                story_bible["characters"].update(recommended["characters"])
            if recommended.get("locations"):
                if "locations" not in story_bible:
                    story_bible["locations"] = {}
                story_bible["locations"].update(recommended["locations"])

        except Exception as e:
            logger.warning(f"Pre-validation failed, continuing: {e}")
            validation_warnings = []

        # ============================================================
        # Phase 3: Generate draft (40%)
        # ============================================================
        await update_task_progress(
            session, task_id, TaskStatus.RUNNING, 40,
            f"Generating draft for chapter {chapter_num}..."
        )

        llm = AsyncLLMClient(model=settings.model_chapter)
        prompt = PromptTemplates.chapter(
            chapter_num=chapter_num,
            blueprint=blueprint,
            author_context=author_context,
            story_bible=story_bible,
            previous_chapters=previous_chapters,
            guidance=task.guidance,
            characters_limit=settings.context_characters_limit,
            prev_ending_chars=settings.context_previous_ending_chars,
            validation_warnings=validation_warnings if validation_warnings else None,
        )

        draft, input_tokens, output_tokens = await llm.generate(
            prompt, max_tokens=16384
        )
        draft_cost = llm.calculate_cost(input_tokens, output_tokens)
        total_costs.append((settings.model_chapter, input_tokens, output_tokens, draft_cost))

        final_text = draft

        # ============================================================
        # Phase 4: Critique (55%)
        # ============================================================
        await update_task_progress(
            session, task_id, TaskStatus.RUNNING, 55,
            f"Critiquing chapter {chapter_num} draft..."
        )

        try:
            critique_llm = AsyncLLMClient(model=settings.model_critique)
            (
                critique_result,
                needs_revision,
                crit_in,
                crit_out,
                crit_cost,
            ) = await _run_critique(
                critique_llm, draft, blueprint, author_context, story_bible
            )
            total_costs.append((settings.model_critique, crit_in, crit_out, crit_cost))

            overall_score = critique_result.get("overall_score", 7)
            logger.info(
                f"Chapter {chapter_num} critique score: {overall_score}/10, "
                f"needs_revision: {needs_revision}"
            )

            # ============================================================
            # Phase 5: Polish if needed (70%)
            # ============================================================
            if needs_revision:
                await update_task_progress(
                    session, task_id, TaskStatus.RUNNING, 70,
                    f"Polishing chapter {chapter_num} (score: {overall_score}/10)..."
                )

                polish_llm = AsyncLLMClient(model=settings.model_polish)
                (
                    polished_text,
                    pol_in,
                    pol_out,
                    pol_cost,
                ) = await _run_polish(
                    polish_llm, draft, critique_result, author_context, blueprint
                )
                total_costs.append((settings.model_polish, pol_in, pol_out, pol_cost))

                final_text = polished_text
                logger.info(f"Chapter {chapter_num} polished after critique")
            else:
                logger.info(f"Chapter {chapter_num} passed critique, no polish needed")

        except Exception as e:
            logger.warning(f"Critique/polish failed, using draft: {e}")
            # Continue with draft if critique fails

        # ============================================================
        # Phase 6: Update story bible (85%)
        # ============================================================
        await update_task_progress(
            session, task_id, TaskStatus.RUNNING, 85,
            f"Updating story bible for chapter {chapter_num}..."
        )

        bible_llm = AsyncLLMClient(model=settings.model_story_bible)
        bible_prompt = PromptTemplates.story_bible_update(
            chapter_num=chapter_num,
            chapter_content=final_text,
            blueprint=blueprint,
            current_bible=story_bible,
        )
        bible_update_raw, bible_in, bible_out = await bible_llm.generate(bible_prompt)
        bible_cost = bible_llm.calculate_cost(bible_in, bible_out)
        total_costs.append((settings.model_story_bible, bible_in, bible_out, bible_cost))

        # Parse and merge bible updates
        bible_updates, bible_errors = _parse_yaml_response(bible_update_raw)
        if bible_errors:
            logger.warning(f"Story bible update parse errors: {bible_errors}")

        # Merge updates into story bible
        if bible_updates:
            for key in ["characters", "locations", "plot_threads"]:
                if key in bible_updates:
                    if key not in story_bible:
                        story_bible[key] = {}
                    story_bible[key].update(bible_updates[key])
            for key in ["timeline", "consistency_notes"]:
                if key in bible_updates and bible_updates[key]:
                    if key not in story_bible:
                        story_bible[key] = []
                    story_bible[key].extend(bible_updates[key])

        # ============================================================
        # Phase 7: Save (95%)
        # ============================================================
        await update_task_progress(
            session, task_id, TaskStatus.RUNNING, 95,
            f"Saving chapter {chapter_num}..."
        )

        service = ProjectService(session)
        word_count = len(final_text.split())
        await service.save_chapter(project.id, chapter_num, final_text, word_count)

        # Save updated story bible as YAML
        try:
            updated_bible_str = yaml.dump(story_bible, default_flow_style=False, allow_unicode=True)
            await service.save_content(project.id, ContentType.STORY_BIBLE, updated_bible_str)
        except Exception as e:
            logger.warning(f"Failed to save story bible: {e}")
            # Save raw update if structured save fails
            await service.save_content(project.id, ContentType.STORY_BIBLE, bible_update_raw)

        await service.update_stage(project.id, ProjectStage.PROSE, current_chapter=chapter_num)

        # Record all costs
        for model, in_tokens, out_tokens, cost in total_costs:
            await record_cost(
                session, project.user_id, project.id,
                model, in_tokens, out_tokens, cost
            )

        # Calculate total cost for logging
        total_cost_sum = sum(c[3] for c in total_costs)
        total_in = sum(c[1] for c in total_costs)
        total_out = sum(c[2] for c in total_costs)
        logger.info(
            f"Chapter {chapter_num} complete: {word_count} words, "
            f"total cost: ${total_cost_sum:.4f} ({total_in} in / {total_out} out tokens)"
        )

        task.result = final_text
        task.status = TaskStatus.AWAITING_APPROVAL
        task.progress_percent = 100
        task.progress_message = f"Chapter {chapter_num} ready ({word_count} words)"
        await session.commit()


@celery_app.task(bind=True)
def generate_essence_task(self, task_id: int):
    """Celery task wrapper for essence generation."""
    try:
        asyncio.run(_run_essence_generation(task_id))
    except Exception as e:
        # Update task with error
        async def update_error():
            AsyncSessionLocal = get_async_session()
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(GenerationTask).where(GenerationTask.id == task_id)
                )
                task = result.scalar_one()
                task.status = TaskStatus.FAILED
                task.error_message = str(e)
                await session.commit()
        asyncio.run(update_error())
        raise


@celery_app.task(bind=True)
def generate_architecture_task(self, task_id: int):
    """Celery task wrapper for architecture generation."""
    try:
        asyncio.run(_run_architecture_generation(task_id))
    except Exception as e:
        async def update_error():
            AsyncSessionLocal = get_async_session()
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(GenerationTask).where(GenerationTask.id == task_id)
                )
                task = result.scalar_one()
                task.status = TaskStatus.FAILED
                task.error_message = str(e)
                await session.commit()
        asyncio.run(update_error())
        raise


@celery_app.task(bind=True)
def generate_blueprint_task(self, task_id: int):
    """Celery task wrapper for blueprint generation."""
    try:
        asyncio.run(_run_blueprint_generation(task_id))
    except Exception as e:
        async def update_error():
            AsyncSessionLocal = get_async_session()
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(GenerationTask).where(GenerationTask.id == task_id)
                )
                task = result.scalar_one()
                task.status = TaskStatus.FAILED
                task.error_message = str(e)
                await session.commit()
        asyncio.run(update_error())
        raise


@celery_app.task(bind=True)
def generate_chapter_task(self, task_id: int):
    """Celery task wrapper for chapter generation."""
    try:
        asyncio.run(_run_chapter_generation(task_id))
    except Exception as e:
        async def update_error():
            AsyncSessionLocal = get_async_session()
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(GenerationTask).where(GenerationTask.id == task_id)
                )
                task = result.scalar_one()
                task.status = TaskStatus.FAILED
                task.error_message = str(e)
                await session.commit()
        asyncio.run(update_error())
        raise
