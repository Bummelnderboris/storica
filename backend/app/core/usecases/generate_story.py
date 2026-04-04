"""
Generate Story Use Case - THE single entry point for story generation.

This orchestrates the entire pipeline from start to finish.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any, Callable, Awaitable
import time

from ..domain import (
    Project,
    Author,
    PipelineRun,
    PhaseResult,
    StoryBible,
    PhaseType,
)
from ..domain.values import (
    PhaseStatus,
    PipelineStatus,
    GenerationConfig,
    CritiqueScore,
    CritiqueResult,
    TokenUsage,
)
from ..ports import LLMPort, StoragePort, EventPort, AuthorPort


@dataclass
class GenerateStoryRequest:
    """Request to generate a story."""
    project_id: int
    author_id: str
    config: GenerationConfig = None

    def __post_init__(self):
        if self.config is None:
            self.config = GenerationConfig()


@dataclass
class GenerateStoryResult:
    """Result of story generation."""
    success: bool
    pipeline_run: PipelineRun
    error: Optional[str] = None


class GenerateStoryUseCase:
    """
    Orchestrates the complete story generation pipeline.

    This is the SINGLE entry point for story generation.
    It coordinates all phases and handles the critique loop.
    """

    def __init__(
        self,
        llm: LLMPort,
        storage: StoragePort,
        events: EventPort,
        authors: AuthorPort,
        prompt_renderer: Callable[[str, Dict[str, Any]], str],
    ):
        """
        Initialize with dependencies (injected).

        Args:
            llm: LLM port for generation
            storage: Storage port for persistence
            events: Event port for broadcasting
            authors: Author port for profiles
            prompt_renderer: Function to render prompt templates
        """
        self.llm = llm
        self.storage = storage
        self.events = events
        self.authors = authors
        self.render_prompt = prompt_renderer

    async def execute(
        self,
        request: GenerateStoryRequest
    ) -> GenerateStoryResult:
        """
        Execute the story generation pipeline.

        Args:
            request: Generation request with project and config

        Returns:
            GenerateStoryResult with pipeline run and status
        """
        # Load project
        project = await self.storage.get_project(request.project_id)
        if not project:
            return GenerateStoryResult(
                success=False,
                pipeline_run=PipelineRun(),
                error=f"Project {request.project_id} not found"
            )

        # Load author
        author = await self.authors.get_author(request.author_id)
        if not author:
            return GenerateStoryResult(
                success=False,
                pipeline_run=PipelineRun(),
                error=f"Author {request.author_id} not found"
            )

        # Initialize pipeline run
        run = PipelineRun(
            project_id=project.id,
            author_id=author.id,
            status=PipelineStatus.RUNNING.value,
            auto_approve=request.config.auto_approve,
            started_at=datetime.utcnow(),
        )

        await self.storage.save_pipeline_run(run)
        await self.events.emit_pipeline_started(project.id, run)

        try:
            # Execute each phase
            run = await self._run_phase(
                run, project, author, request.config,
                PhaseType.AUTHOR_LOADING,
                self._phase_author_loading
            )

            run = await self._run_phase(
                run, project, author, request.config,
                PhaseType.TOPIC_EXPLORATION,
                self._phase_topic_exploration
            )

            run = await self._run_phase(
                run, project, author, request.config,
                PhaseType.THESIS_DEVELOPMENT,
                self._phase_thesis_development
            )

            run = await self._run_phase(
                run, project, author, request.config,
                PhaseType.CHARACTER_DERIVATION,
                self._phase_character_derivation
            )

            run = await self._run_phase(
                run, project, author, request.config,
                PhaseType.STORY_ARCHITECTURE,
                self._phase_story_architecture
            )

            run = await self._run_phase(
                run, project, author, request.config,
                PhaseType.BLUEPRINT_PLANNING,
                self._phase_blueprint_planning
            )

            # Prose generation (chapter by chapter)
            run = await self._run_prose_generation(
                run, project, author, request.config
            )

            # Final consistency check
            run = await self._run_phase(
                run, project, author, request.config,
                PhaseType.CONSISTENCY_CHECK,
                self._phase_consistency_check
            )

            # Complete
            run.status = PipelineStatus.COMPLETED.value
            run.completed_at = datetime.utcnow()
            await self.storage.save_pipeline_run(run)
            await self.events.emit_pipeline_completed(project.id, run)

            return GenerateStoryResult(success=True, pipeline_run=run)

        except PipelinePausedError:
            # Pipeline paused for approval
            run.status = PipelineStatus.AWAITING_APPROVAL.value
            await self.storage.save_pipeline_run(run)
            return GenerateStoryResult(success=True, pipeline_run=run)

        except Exception as e:
            # Handle failure
            run.status = PipelineStatus.FAILED.value
            await self.storage.save_pipeline_run(run)
            await self.events.emit_error(project.id, str(e), run.current_phase.value if run.current_phase else None)
            return GenerateStoryResult(
                success=False,
                pipeline_run=run,
                error=str(e)
            )

    async def _run_phase(
        self,
        run: PipelineRun,
        project: Project,
        author: Author,
        config: GenerationConfig,
        phase_type: PhaseType,
        phase_fn: Callable,
    ) -> PipelineRun:
        """Run a single phase."""
        run.current_phase = phase_type
        await self.events.emit_phase_started(project.id, phase_type.value)

        start_time = time.time()

        result = PhaseResult(
            phase=phase_type,
            status=PhaseStatus.RUNNING.value,
            started_at=datetime.utcnow(),
        )

        try:
            # Execute phase
            output, usage = await phase_fn(project, author, config)

            # Update result
            result.status = PhaseStatus.COMPLETED.value
            result.output = output
            result.input_tokens = usage.input_tokens
            result.output_tokens = usage.output_tokens
            result.execution_time_ms = int((time.time() - start_time) * 1000)
            result.completed_at = datetime.utcnow()

            # Update run totals
            run.total_input_tokens += usage.input_tokens
            run.total_output_tokens += usage.output_tokens
            run.estimated_cost_usd = TokenUsage(
                run.total_input_tokens,
                run.total_output_tokens
            ).estimated_cost_usd

            run.phases.append(result)
            await self.storage.save_phase_result(project.id, result)
            await self.events.emit_phase_completed(project.id, result)

            # Check if approval needed
            if not config.auto_approve and phase_type != PhaseType.AUTHOR_LOADING:
                run.status = PipelineStatus.AWAITING_APPROVAL.value
                await self.storage.save_pipeline_run(run)
                await self.events.emit_approval_required(
                    project.id,
                    phase_type.value,
                    output
                )
                raise PipelinePausedError("Awaiting approval")

            return run

        except PipelinePausedError:
            raise

        except Exception as e:
            result.status = PhaseStatus.FAILED.value
            result.error = str(e)
            result.execution_time_ms = int((time.time() - start_time) * 1000)
            run.phases.append(result)
            await self.events.emit_phase_failed(project.id, phase_type.value, str(e))
            raise

    # Phase implementations

    async def _phase_author_loading(
        self,
        project: Project,
        author: Author,
        config: GenerationConfig,
    ) -> tuple[Dict[str, Any], TokenUsage]:
        """Load author profile (no LLM needed)."""
        return {
            "author_id": author.id,
            "name": author.name,
            "language": author.language,
            "style_guide_preview": author.get_style_guide()[:500],
        }, TokenUsage(0, 0)

    async def _phase_topic_exploration(
        self,
        project: Project,
        author: Author,
        config: GenerationConfig,
    ) -> tuple[Dict[str, Any], TokenUsage]:
        """Explore story topics through author's lens."""
        prompt = self.render_prompt("topic_exploration", {
            "story_dna": project.story_dna.to_dict() if project.story_dna else {},
            "author_philosophy": author.philosophy,
            "author_name": author.name,
        })

        response = await self.llm.generate(
            prompt=prompt,
            system=f"You are analyzing a story concept through the lens of {author.name}. "
                   f"Write in {author.language}.",
            model=config.model_default,
        )

        output = self._parse_structured_output(response.content)
        project.topic_analysis = output
        await self.storage.save_project(project)

        return output, TokenUsage(response.input_tokens, response.output_tokens)

    async def _phase_thesis_development(
        self,
        project: Project,
        author: Author,
        config: GenerationConfig,
    ) -> tuple[Dict[str, Any], TokenUsage]:
        """Develop the story's central thesis."""
        prompt = self.render_prompt("thesis_development", {
            "story_dna": project.story_dna.to_dict() if project.story_dna else {},
            "topic_analysis": project.topic_analysis or {},
            "author_philosophy": author.philosophy,
            "author_name": author.name,
        })

        response = await self.llm.generate(
            prompt=prompt,
            system=f"You are {author.name}, developing a story's thesis. "
                   f"Write in {author.language}.",
            model=config.model_default,
        )

        output = self._parse_structured_output(response.content)
        project.thesis = output
        await self.storage.save_project(project)

        return output, TokenUsage(response.input_tokens, response.output_tokens)

    async def _phase_character_derivation(
        self,
        project: Project,
        author: Author,
        config: GenerationConfig,
    ) -> tuple[Dict[str, Any], TokenUsage]:
        """Derive characters from thesis."""
        prompt = self.render_prompt("character_derivation", {
            "story_dna": project.story_dna.to_dict() if project.story_dna else {},
            "thesis": project.thesis or {},
            "author_character_patterns": author.patterns.get("characters", {}),
            "author_name": author.name,
        })

        response = await self.llm.generate(
            prompt=prompt,
            system=f"You are {author.name}, creating characters. "
                   f"Write in {author.language}.",
            model=config.model_default,
        )

        output = self._parse_structured_output(response.content)
        project.character_system = output
        await self.storage.save_project(project)

        return output, TokenUsage(response.input_tokens, response.output_tokens)

    async def _phase_story_architecture(
        self,
        project: Project,
        author: Author,
        config: GenerationConfig,
    ) -> tuple[Dict[str, Any], TokenUsage]:
        """Design overall story structure."""
        prompt = self.render_prompt("story_architecture", {
            "story_dna": project.story_dna.to_dict() if project.story_dna else {},
            "thesis": project.thesis or {},
            "characters": project.character_system or {},
            "author_structure_patterns": author.patterns.get("structure", {}),
            "target_chapters": project.total_chapters,
            "author_name": author.name,
        })

        response = await self.llm.generate(
            prompt=prompt,
            system=f"You are {author.name}, architecting a story. "
                   f"Write in {author.language}.",
            model=config.model_default,
        )

        output = self._parse_structured_output(response.content)
        project.architecture = output
        await self.storage.save_project(project)

        return output, TokenUsage(response.input_tokens, response.output_tokens)

    async def _phase_blueprint_planning(
        self,
        project: Project,
        author: Author,
        config: GenerationConfig,
    ) -> tuple[Dict[str, Any], TokenUsage]:
        """Create chapter blueprints."""
        blueprints = []
        total_usage = TokenUsage(0, 0)

        for chapter_num in range(1, project.total_chapters + 1):
            prompt = self.render_prompt("chapter_blueprint", {
                "chapter_number": chapter_num,
                "total_chapters": project.total_chapters,
                "architecture": project.architecture or {},
                "characters": project.character_system or {},
                "previous_blueprints": blueprints,
                "author_name": author.name,
            })

            response = await self.llm.generate(
                prompt=prompt,
                system=f"You are {author.name}, planning chapter {chapter_num}. "
                       f"Write in {author.language}.",
                model=config.model_default,
            )

            blueprint = self._parse_structured_output(response.content)
            blueprint["chapter_number"] = chapter_num
            blueprints.append(blueprint)

            total_usage = total_usage + TokenUsage(
                response.input_tokens,
                response.output_tokens
            )

        return {"blueprints": blueprints}, total_usage

    async def _run_prose_generation(
        self,
        run: PipelineRun,
        project: Project,
        author: Author,
        config: GenerationConfig,
    ) -> PipelineRun:
        """Generate prose for all chapters with critique loop."""
        run.current_phase = PhaseType.PROSE_GENERATION

        # Get story bible
        story_bible = await self.storage.get_story_bible(project.id)
        if not story_bible:
            story_bible = StoryBible(project_id=project.id)

        # Get blueprints from last phase
        blueprints = []
        for phase in run.phases:
            if phase.phase == PhaseType.BLUEPRINT_PLANNING and phase.output:
                blueprints = phase.output.get("blueprints", [])

        for chapter_num in range(1, project.total_chapters + 1):
            run.current_chapter = chapter_num
            await self.events.emit_phase_started(
                project.id,
                f"prose_generation_chapter_{chapter_num}"
            )

            blueprint = blueprints[chapter_num - 1] if chapter_num <= len(blueprints) else {}

            # Critique loop
            prose = ""
            for iteration in range(1, config.max_iterations + 1):
                # Generate/revise prose
                if iteration == 1:
                    prose, usage = await self._generate_chapter_prose(
                        project, author, config, chapter_num, blueprint, story_bible
                    )
                else:
                    prose, usage = await self._revise_chapter_prose(
                        project, author, config, chapter_num, prose,
                        critique_result, story_bible
                    )

                run.total_input_tokens += usage.input_tokens
                run.total_output_tokens += usage.output_tokens

                # Critique
                critique_result, critique_usage = await self._critique_prose(
                    project, author, config, prose, blueprint
                )

                run.total_input_tokens += critique_usage.input_tokens
                run.total_output_tokens += critique_usage.output_tokens

                await self.events.emit_critique_result(
                    project.id, chapter_num, iteration, critique_result
                )

                if critique_result.passes_threshold:
                    break

            # Save chapter
            from ..domain import Chapter
            chapter = Chapter(
                number=chapter_num,
                content=prose,
                word_count=len(prose.split()),
                blueprint=blueprint,
                final_score=critique_result.overall_score,
                status="completed",
            )
            await self.storage.save_chapter(project.id, chapter)

            # Update story bible
            story_bible = await self._update_story_bible(
                project, chapter, story_bible
            )

        return run

    async def _generate_chapter_prose(
        self,
        project: Project,
        author: Author,
        config: GenerationConfig,
        chapter_num: int,
        blueprint: Dict[str, Any],
        story_bible: StoryBible,
    ) -> tuple[str, TokenUsage]:
        """Generate initial chapter prose."""
        prompt = self.render_prompt("prose_writing", {
            "chapter_number": chapter_num,
            "blueprint": blueprint,
            "story_bible": story_bible.to_context_string(),
            "author_style_guide": author.get_style_guide(),
            "author_name": author.name,
        })

        response = await self.llm.generate(
            prompt=prompt,
            system=f"You ARE {author.name}. Write this chapter in your voice, "
                   f"in {author.language}. No meta-commentary.",
            max_tokens=config.max_tokens_per_chapter,
            temperature=config.temperature,
            model=config.model_prose,
        )

        return response.content, TokenUsage(response.input_tokens, response.output_tokens)

    async def _critique_prose(
        self,
        project: Project,
        author: Author,
        config: GenerationConfig,
        prose: str,
        blueprint: Dict[str, Any],
    ) -> tuple[CritiqueResult, TokenUsage]:
        """Critique chapter prose."""
        prompt = self.render_prompt("prose_critique", {
            "prose": prose,
            "blueprint": blueprint,
            "critique_rubric": author.critique_rubric,
            "author_name": author.name,
        })

        response = await self.llm.generate(
            prompt=prompt,
            system=f"You are a literary critic evaluating prose meant to emulate {author.name}.",
            model=config.model_default,
        )

        # Parse critique scores
        parsed = self._parse_structured_output(response.content)
        scores = [
            CritiqueScore(
                category=s.get("category", "unknown"),
                score=float(s.get("score", 5)),
                feedback=s.get("feedback", ""),
                weight=s.get("weight", 1.0),
            )
            for s in parsed.get("scores", [])
        ]

        result = CritiqueResult.from_scores(scores, config.passing_threshold)

        return result, TokenUsage(response.input_tokens, response.output_tokens)

    async def _revise_chapter_prose(
        self,
        project: Project,
        author: Author,
        config: GenerationConfig,
        chapter_num: int,
        prose: str,
        critique: CritiqueResult,
        story_bible: StoryBible,
    ) -> tuple[str, TokenUsage]:
        """Revise chapter based on critique."""
        prompt = self.render_prompt("prose_revision", {
            "original_prose": prose,
            "critique_issues": list(critique.issues),
            "revision_priorities": list(critique.revision_priorities),
            "author_style_guide": author.get_style_guide(),
            "author_name": author.name,
        })

        response = await self.llm.generate(
            prompt=prompt,
            system=f"You ARE {author.name}. Revise this chapter addressing the feedback, "
                   f"in {author.language}.",
            max_tokens=config.max_tokens_per_chapter,
            temperature=config.temperature,
            model=config.model_prose,
        )

        return response.content, TokenUsage(response.input_tokens, response.output_tokens)

    async def _update_story_bible(
        self,
        project: Project,
        chapter,
        story_bible: StoryBible,
    ) -> StoryBible:
        """Update story bible after chapter completion."""
        # This would use LLM to extract entities, but simplified here
        story_bible.last_updated = datetime.utcnow()
        await self.storage.save_story_bible(story_bible)
        return story_bible

    async def _phase_consistency_check(
        self,
        project: Project,
        author: Author,
        config: GenerationConfig,
    ) -> tuple[Dict[str, Any], TokenUsage]:
        """Final consistency check."""
        story_bible = await self.storage.get_story_bible(project.id)

        prompt = self.render_prompt("consistency_check", {
            "story_bible": story_bible.to_context_string() if story_bible else "",
            "chapter_count": project.total_chapters,
        })

        response = await self.llm.generate(
            prompt=prompt,
            system="You are checking story consistency.",
            model=config.model_default,
        )

        return self._parse_structured_output(response.content), TokenUsage(
            response.input_tokens, response.output_tokens
        )

    def _parse_structured_output(self, content: str) -> Dict[str, Any]:
        """Parse structured output from LLM response."""
        import json
        import re

        # Try to find JSON in the response
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Return as raw content
        return {"raw_content": content}


class PipelinePausedError(Exception):
    """Raised when pipeline is paused for approval."""
    pass
