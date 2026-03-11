"""Generation tasks for Celery."""

import asyncio
import re
from typing import Optional

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

# Import prompts from original litai
import sys
from pathlib import Path

# Add original litai to path for prompt imports
litai_path = Path(__file__).parent.parent.parent.parent.parent / "src"
if str(litai_path) not in sys.path:
    sys.path.insert(0, str(litai_path))

from litai.llm.prompts import PromptTemplates

settings = get_settings()


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
        llm = AsyncLLMClient()
        prompt = PromptTemplates.essence(
            seed=project.seed or "A story worth telling",
            author_profile=author_context,
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
            settings.default_model, input_tokens, output_tokens, cost
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

        llm = AsyncLLMClient()
        prompt = PromptTemplates.architecture(
            essence=essence,
            author_profile=author_context,
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
            settings.default_model, input_tokens, output_tokens, cost
        )

        task.result = text
        task.status = TaskStatus.AWAITING_APPROVAL
        task.progress_percent = 100
        task.progress_message = f"Ready for approval ({total_chapters} chapters planned)"
        await session.commit()


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

        llm = AsyncLLMClient()
        prompt = PromptTemplates.blueprint(
            chapter_num=chapter_num,
            architecture=architecture,
            author_profile=author_context,
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
            settings.default_model, input_tokens, output_tokens, cost
        )

        task.result = text
        task.status = TaskStatus.AWAITING_APPROVAL
        task.progress_percent = 100
        task.progress_message = f"Blueprint {chapter_num} ready for approval"
        await session.commit()


async def _run_chapter_generation(task_id: int):
    """Generate chapter prose."""
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

        # Get blueprint for this chapter
        blueprint = await adapter.get_blueprint(chapter_num)
        if not blueprint:
            task.status = TaskStatus.FAILED
            task.error_message = f"Blueprint for chapter {chapter_num} not found."
            await session.commit()
            return

        # Get story bible and previous chapters
        story_bible = await adapter.get_story_bible() or ""
        previous_chapters = await adapter.get_previous_chapters(chapter_num, limit=2)

        author_service = AuthorService()
        author_context = author_service.get_prompt_context(project.author_id)

        await update_task_progress(
            session, task_id, TaskStatus.RUNNING, 30,
            f"Generating chapter {chapter_num} prose..."
        )

        llm = AsyncLLMClient()
        prompt = PromptTemplates.chapter(
            chapter_num=chapter_num,
            blueprint=blueprint,
            author_profile=author_context,
            story_bible=story_bible,
            previous_chapters=previous_chapters,
            guidance=task.guidance,
        )

        text, input_tokens, output_tokens = await llm.generate(
            prompt, max_tokens=16384  # Longer for prose
        )
        cost = llm.calculate_cost(input_tokens, output_tokens)

        await update_task_progress(
            session, task_id, TaskStatus.RUNNING, 70, "Updating story bible..."
        )

        # Update story bible
        bible_prompt = PromptTemplates.story_bible_update(
            chapter_num=chapter_num,
            chapter_content=text,
            blueprint=blueprint,
            current_bible=story_bible,
        )
        bible_update, bible_in, bible_out = await llm.generate(bible_prompt)
        cost += llm.calculate_cost(bible_in, bible_out)

        await update_task_progress(
            session, task_id, TaskStatus.RUNNING, 85, "Saving chapter..."
        )

        service = ProjectService(session)
        word_count = len(text.split())
        await service.save_chapter(project.id, chapter_num, text, word_count)
        await service.save_content(project.id, ContentType.STORY_BIBLE, bible_update)
        await service.update_stage(project.id, ProjectStage.PROSE, current_chapter=chapter_num)

        # Record costs
        await record_cost(
            session, project.user_id, project.id,
            settings.default_model, input_tokens + bible_in, output_tokens + bible_out, cost
        )

        task.result = text
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
