"""
Generate Story Use Case - orchestrates the agent pipeline.

This is the SINGLE entry point for story generation. It delegates all
creative work to specialised agents and manages state, flow, approval
gates, cost tracking, and the story bible.
"""

import json
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any, List

from ..domain import (
    Project,
    Author,
    PipelineRun,
    PhaseResult,
    StoryBible,
    PhaseType,
    Chapter,
)
from ..domain.values import (
    PhaseStatus,
    PipelineStatus,
    GenerationConfig,
    TokenUsage,
)
from ..ports import LLMPort, StoragePort, EventPort, AuthorPort

from ...agents import AgentContext, AgentPhase, AgentRegistry
from ...agents.phase1_topic.schema import TopicExplorationInput
from ...agents.phase2_thesis.schema import ThesisDevelopmentInput
from ...agents.phase3_character.schema import CharacterDerivationInput
from ...agents.phase4_architecture.schema import StoryArchitectureInput
from ...agents.phase5_blueprint.schema import BlueprintInput
from ...agents.phase6_prose.schema import ProseInput
from ...agents.phase6_prose.loop import ProseGenerationLoop, LoopCallbacks
from ...agents.phase7_consistency.schema import ConsistencyInput
from ...agents.phase7_consistency.story_bible import StoryBible as AgentStoryBible


# ---------------------------------------------------------------------------
# Map domain PhaseType -> agent AgentPhase (different enum values)
# ---------------------------------------------------------------------------
PHASE_MAP: Dict[PhaseType, AgentPhase] = {
    PhaseType.TOPIC_EXPLORATION: AgentPhase.TOPIC_EXPLORATION,
    PhaseType.THESIS_DEVELOPMENT: AgentPhase.THESIS_DEVELOPMENT,
    PhaseType.CHARACTER_DERIVATION: AgentPhase.CHARACTER_DERIVATION,
    PhaseType.STORY_ARCHITECTURE: AgentPhase.STORY_ARCHITECTURE,
    PhaseType.BLUEPRINT_PLANNING: AgentPhase.CHAPTER_BLUEPRINTS,
    PhaseType.CONSISTENCY_CHECK: AgentPhase.CONSISTENCY_CHECK,
}

# Phases that need user approval before the pipeline continues
APPROVAL_PHASES = {
    PhaseType.TOPIC_EXPLORATION,
    PhaseType.THESIS_DEVELOPMENT,
    PhaseType.CHARACTER_DERIVATION,
    PhaseType.STORY_ARCHITECTURE,
    PhaseType.BLUEPRINT_PLANNING,
}


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


class PipelinePausedError(Exception):
    """Raised when the pipeline is paused for approval."""
    pass


class GenerateStoryUseCase:
    """
    Orchestrates the complete story generation pipeline.

    All creative work is delegated to registered agents.  This class
    manages sequencing, state persistence, cost tracking, approval
    gates, story-bible updates and pipeline resume.
    """

    def __init__(
        self,
        llm: LLMPort,
        storage: StoragePort,
        events: EventPort,
        authors: AuthorPort,
        prompt_engine,
    ):
        self.llm = llm
        self.storage = storage
        self.events = events
        self.authors = authors
        self.prompt_engine = prompt_engine

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_agent(self, agent_phase: AgentPhase):
        """Get an agent from the registry, creating it if needed."""
        agent = AgentRegistry.get_agent(
            agent_phase, self.llm, self.prompt_engine, cached=True,
        )
        if agent is None:
            raise RuntimeError(f"No agent registered for {agent_phase.value}")
        return agent

    def _build_context(
        self, project: Project, author: Author,
    ) -> AgentContext:
        """Build an AgentContext populated with project + author data."""
        return AgentContext(
            project_id=project.id,
            author_id=author.id,
            author_profile={
                "id": author.id,
                "name": author.name,
                "language": author.language,
                "philosophy": author.philosophy,
                "style": author.style,
                "patterns": author.patterns,
                "critique_rubric": author.critique_rubric,
            },
            story_dna=project.story_dna.to_dict() if project.story_dna else {},
        )

    def _completed_phases(self, run: PipelineRun) -> Dict[PhaseType, Dict[str, Any]]:
        """Return a dict of phase -> output for already-completed phases."""
        result = {}
        for pr in run.phases:
            if pr.status == PhaseStatus.COMPLETED.value and pr.output:
                result[pr.phase] = pr.output
        return result

    def _track_tokens(self, run: PipelineRun, agent_result) -> None:
        """Accumulate token usage from an agent result onto the run."""
        run.total_input_tokens += agent_result.input_tokens
        run.total_output_tokens += agent_result.output_tokens
        run.estimated_cost_usd = TokenUsage(
            run.total_input_tokens, run.total_output_tokens,
        ).estimated_cost_usd

    def _to_serialisable(self, output) -> Dict[str, Any]:
        """Convert a Pydantic model or dict to a JSON-safe dict."""
        if hasattr(output, "model_dump"):
            return output.model_dump()
        if isinstance(output, dict):
            return output
        return {"raw": str(output)}

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def execute(
        self, request: GenerateStoryRequest,
    ) -> GenerateStoryResult:
        project = await self.storage.get_project(request.project_id)
        if not project:
            return GenerateStoryResult(
                success=False, pipeline_run=PipelineRun(),
                error=f"Project {request.project_id} not found",
            )

        author = await self.authors.get_author(request.author_id)
        if not author:
            return GenerateStoryResult(
                success=False, pipeline_run=PipelineRun(),
                error=f"Author {request.author_id} not found",
            )

        config = request.config
        context = self._build_context(project, author)

        # Resume or create pipeline run
        run = await self.storage.get_pipeline_run(project.id)
        if run and run.status in (
            PipelineStatus.RUNNING.value,
            PipelineStatus.AWAITING_APPROVAL.value,
        ):
            # Resuming an existing run
            run.status = PipelineStatus.RUNNING.value
        else:
            run = PipelineRun(
                project_id=project.id,
                author_id=author.id,
                status=PipelineStatus.RUNNING.value,
                auto_approve=config.auto_approve,
                started_at=datetime.utcnow(),
            )

        await self.storage.save_pipeline_run(run)
        await self.events.emit_pipeline_started(project.id, run)

        try:
            completed = self._completed_phases(run)

            # ----- Phase 0: Author Loading (no agent, no LLM) -----
            if PhaseType.AUTHOR_LOADING not in completed:
                phase_output = self._run_author_loading(author)
                completed[PhaseType.AUTHOR_LOADING] = phase_output
                run = await self._record_phase(
                    run, project.id, PhaseType.AUTHOR_LOADING,
                    phase_output, TokenUsage(0, 0),
                )

            # ----- Phase 1: Topic Exploration -----
            if PhaseType.TOPIC_EXPLORATION not in completed:
                result = await self._run_topic_exploration(
                    context, project, author, config, run,
                )
                completed[PhaseType.TOPIC_EXPLORATION] = result
            context.previous_outputs["topic_exploration"] = completed[PhaseType.TOPIC_EXPLORATION]

            # ----- Phase 2: Thesis Development -----
            if PhaseType.THESIS_DEVELOPMENT not in completed:
                result = await self._run_thesis_development(
                    context, project, completed, config, run,
                )
                completed[PhaseType.THESIS_DEVELOPMENT] = result
            context.previous_outputs["thesis"] = completed[PhaseType.THESIS_DEVELOPMENT]

            # ----- Phase 3: Character Derivation -----
            if PhaseType.CHARACTER_DERIVATION not in completed:
                result = await self._run_character_derivation(
                    context, project, author, completed, config, run,
                )
                completed[PhaseType.CHARACTER_DERIVATION] = result
            context.previous_outputs["characters"] = completed[PhaseType.CHARACTER_DERIVATION]

            # ----- Phase 4: Story Architecture -----
            if PhaseType.STORY_ARCHITECTURE not in completed:
                result = await self._run_story_architecture(
                    context, project, author, completed, config, run,
                )
                completed[PhaseType.STORY_ARCHITECTURE] = result
            context.previous_outputs["architecture"] = completed[PhaseType.STORY_ARCHITECTURE]

            # ----- Phase 5: Blueprint Planning (per chapter) -----
            if PhaseType.BLUEPRINT_PLANNING not in completed:
                result = await self._run_blueprint_planning(
                    context, project, author, completed, config, run,
                )
                completed[PhaseType.BLUEPRINT_PLANNING] = result
            context.previous_outputs["blueprints"] = completed[PhaseType.BLUEPRINT_PLANNING]

            # ----- Phase 6: Prose Generation (per chapter + consistency) -----
            if PhaseType.PROSE_GENERATION not in completed:
                await self._run_prose_generation(
                    context, project, author, completed, config, run,
                )

            # ----- Phase 7: Final Consistency Check -----
            if PhaseType.CONSISTENCY_CHECK not in completed:
                await self._run_final_consistency_check(
                    context, project, config, run,
                )

            # Complete
            run.status = PipelineStatus.COMPLETED.value
            run.completed_at = datetime.utcnow()
            await self.storage.save_pipeline_run(run)
            await self.events.emit_pipeline_completed(project.id, run)

            return GenerateStoryResult(success=True, pipeline_run=run)

        except PipelinePausedError:
            run.status = PipelineStatus.AWAITING_APPROVAL.value
            await self.storage.save_pipeline_run(run)
            return GenerateStoryResult(success=True, pipeline_run=run)

        except Exception as e:
            run.status = PipelineStatus.FAILED.value
            await self.storage.save_pipeline_run(run)
            await self.events.emit_error(
                project.id, str(e),
                run.current_phase.value if run.current_phase else None,
            )
            return GenerateStoryResult(
                success=False, pipeline_run=run, error=str(e),
            )

    # ------------------------------------------------------------------
    # Phase implementations
    # ------------------------------------------------------------------

    def _run_author_loading(self, author: Author) -> Dict[str, Any]:
        """Phase 0 — load author profile. No LLM, no agent."""
        return {
            "author_id": author.id,
            "name": author.name,
            "language": author.language,
            "style_guide_preview": author.get_style_guide()[:500],
        }

    async def _run_topic_exploration(
        self, context, project, author, config, run,
    ) -> Dict[str, Any]:
        """Phase 1 — explore the story spark through the author's lens."""
        spark = project.story_dna.spark if project.story_dna else {}
        genre = project.story_dna.genre if project.story_dna else {}

        input_data = TopicExplorationInput(
            story_spark=spark.get("description", str(spark)),
            genre=genre.get("primary_genre", str(genre)),
            subgenres=genre.get("subgenres", []),
        )

        output, usage = await self._execute_agent(
            PhaseType.TOPIC_EXPLORATION, input_data, context, run,
        )

        output_dict = self._to_serialisable(output)
        project.topic_analysis = output_dict
        await self.storage.save_project(project)

        await self._approval_gate(
            PhaseType.TOPIC_EXPLORATION, output_dict, config, run, project.id,
        )
        return output_dict

    async def _run_thesis_development(
        self, context, project, completed, config, run,
    ) -> Dict[str, Any]:
        """Phase 2 — develop the central thesis."""
        topic = completed.get(PhaseType.TOPIC_EXPLORATION, {})
        dna = project.story_dna.to_dict() if project.story_dna else {}

        input_data = ThesisDevelopmentInput(
            topic_exploration=topic.get("raw_exploration", json.dumps(topic)),
            story_dna_summary=json.dumps(dna, indent=2),
        )

        output, usage = await self._execute_agent(
            PhaseType.THESIS_DEVELOPMENT, input_data, context, run,
        )

        output_dict = self._to_serialisable(output)
        project.thesis = output_dict
        await self.storage.save_project(project)

        await self._approval_gate(
            PhaseType.THESIS_DEVELOPMENT, output_dict, config, run, project.id,
        )
        return output_dict

    async def _run_character_derivation(
        self, context, project, author, completed, config, run,
    ) -> Dict[str, Any]:
        """Phase 3 — derive characters from thesis."""
        thesis = completed.get(PhaseType.THESIS_DEVELOPMENT, {})
        dna = project.story_dna.to_dict() if project.story_dna else {}
        char_patterns = author.patterns.get("characters", {})

        input_data = CharacterDerivationInput(
            story_thesis=thesis.get("central_thesis", json.dumps(thesis)),
            story_dna_characters=json.dumps(dna.get("characters", {}), indent=2),
            author_character_patterns=json.dumps(char_patterns, indent=2),
        )

        output, usage = await self._execute_agent(
            PhaseType.CHARACTER_DERIVATION, input_data, context, run,
        )

        output_dict = self._to_serialisable(output)
        project.character_system = output_dict
        await self.storage.save_project(project)

        await self._approval_gate(
            PhaseType.CHARACTER_DERIVATION, output_dict, config, run, project.id,
        )
        return output_dict

    async def _run_story_architecture(
        self, context, project, author, completed, config, run,
    ) -> Dict[str, Any]:
        """Phase 4 — design the story structure."""
        thesis = completed.get(PhaseType.THESIS_DEVELOPMENT, {})
        characters = completed.get(PhaseType.CHARACTER_DERIVATION, {})
        dna = project.story_dna.to_dict() if project.story_dna else {}
        structure = dna.get("structure", {})

        input_data = StoryArchitectureInput(
            story_thesis=thesis.get("central_thesis", json.dumps(thesis)),
            characters=json.dumps(characters, indent=2),
            structure_type=structure.get("structure_type", "three_act"),
            chapter_count=project.total_chapters,
        )

        output, usage = await self._execute_agent(
            PhaseType.STORY_ARCHITECTURE, input_data, context, run,
        )

        output_dict = self._to_serialisable(output)
        project.architecture = output_dict
        await self.storage.save_project(project)

        await self._approval_gate(
            PhaseType.STORY_ARCHITECTURE, output_dict, config, run, project.id,
        )
        return output_dict

    async def _run_blueprint_planning(
        self, context, project, author, completed, config, run,
    ) -> Dict[str, Any]:
        """Phase 5 — generate a detailed blueprint for every chapter."""
        architecture = completed.get(PhaseType.STORY_ARCHITECTURE, {})
        characters = completed.get(PhaseType.CHARACTER_DERIVATION, {})
        chapter_pacing = architecture.get("chapter_pacing", [])

        run.current_phase = PhaseType.BLUEPRINT_PLANNING
        await self.events.emit_phase_started(project.id, PhaseType.BLUEPRINT_PLANNING.value)
        start = time.time()
        total_usage = TokenUsage(0, 0)

        agent = self._get_agent(PHASE_MAP[PhaseType.BLUEPRINT_PLANNING])
        blueprints: List[Dict[str, Any]] = []

        # Initialise the story bible for this project
        story_bible = await self.storage.get_story_bible(project.id)

        for chapter_num in range(1, project.total_chapters + 1):
            # Derive chapter purpose from architecture/pacing
            pacing_info = next(
                (cp for cp in chapter_pacing if cp.get("chapter") == chapter_num),
                {},
            )
            purpose = pacing_info.get("focus", f"Chapter {chapter_num}")

            prev_summary = ""
            if blueprints:
                prev_bp = blueprints[-1]
                prev_summary = prev_bp.get("raw_blueprint", json.dumps(prev_bp))[:800]

            input_data = BlueprintInput(
                chapter_index=chapter_num,
                chapter_purpose=purpose,
                story_architecture=json.dumps(architecture, indent=2),
                characters=json.dumps(characters, indent=2),
                previous_chapter_summary=prev_summary or "This is the first chapter.",
                story_bible=story_bible.to_context_string() if story_bible else "No entries yet.",
            )

            result = await agent.execute(input_data, context)
            if not result.success:
                raise RuntimeError(f"Blueprint for chapter {chapter_num} failed: {result.error}")

            bp_dict = self._to_serialisable(result.output)
            bp_dict["chapter_number"] = chapter_num
            blueprints.append(bp_dict)
            total_usage = total_usage + TokenUsage(result.input_tokens, result.output_tokens)

        output_dict = {"blueprints": blueprints}
        run = await self._record_phase(
            run, project.id, PhaseType.BLUEPRINT_PLANNING, output_dict, total_usage,
        )

        await self._approval_gate(
            PhaseType.BLUEPRINT_PLANNING, output_dict, config, run, project.id,
        )
        return output_dict

    async def _run_prose_generation(
        self, context, project, author, completed, config, run,
    ) -> None:
        """
        Phase 6 — write every chapter.

        For each chapter:
        1. Run ProseGenerationLoop (reason -> write -> critique -> revise)
        2. Run ConsistencyGuardian to update story bible
        3. Save chapter
        """
        run.current_phase = PhaseType.PROSE_GENERATION
        await self.events.emit_phase_started(project.id, PhaseType.PROSE_GENERATION.value)

        blueprints_data = completed.get(PhaseType.BLUEPRINT_PLANNING, {})
        blueprints = blueprints_data.get("blueprints", [])

        # Load or create story bible
        story_bible = await self.storage.get_story_bible(project.id)
        if not story_bible:
            story_bible = StoryBible(project_id=project.id)
            await self.storage.save_story_bible(story_bible)

        # Agent story bible for rich tracking
        agent_bible = AgentStoryBible()

        prose_loop = ProseGenerationLoop(
            llm_service=self.llm,
            prompt_engine=self.prompt_engine,
            max_iterations=config.max_iterations,
            passing_threshold=config.passing_threshold,
        )

        consistency_agent = self._get_agent(PHASE_MAP[PhaseType.CONSISTENCY_CHECK])

        # Get already-completed chapters for resume support
        existing_chapters = await self.storage.list_chapters(project.id)
        completed_numbers = {ch.number for ch in existing_chapters}

        total_usage = TokenUsage(0, 0)

        for chapter_num in range(1, project.total_chapters + 1):
            if chapter_num in completed_numbers:
                # Chapter already written (resume scenario) — feed its content
                # into the story bible and skip generation.
                existing = await self.storage.get_chapter(project.id, chapter_num)
                if existing and existing.content:
                    await self._update_story_bible_from_chapter(
                        context, consistency_agent, agent_bible,
                        chapter_num, existing.content,
                    )
                continue

            run.current_chapter = chapter_num
            await self.events.emit_phase_started(
                project.id, f"prose_chapter_{chapter_num}",
            )

            blueprint = blueprints[chapter_num - 1] if chapter_num <= len(blueprints) else {}
            blueprint_text = blueprint.get("raw_blueprint", json.dumps(blueprint, indent=2))

            # Build previous chapter summaries for context
            prev_chapters_context = await self._build_previous_context(project.id, chapter_num)
            bible_text = agent_bible.to_prompt_summary() if agent_bible.data.characters else "No entries yet."
            if prev_chapters_context:
                bible_text = f"{bible_text}\n\n## Previous Chapter Summary\n{prev_chapters_context}"

            prose_input = ProseInput(
                chapter_blueprint=blueprint_text,
                story_bible=bible_text,
                author_style_guide=author.get_style_guide(),
                author_language=author.language,
            )

            # Callbacks for real-time events
            callbacks = LoopCallbacks(
                on_writing_start=lambda it: None,
                on_critique_complete=lambda score, passes: None,
            )

            loop_result = await prose_loop.run(prose_input, context, callbacks)

            # Track tokens from context
            ch_usage = TokenUsage(context.input_tokens, context.output_tokens)
            total_usage = total_usage + ch_usage
            # Reset context counters for next chapter
            context.input_tokens = 0
            context.output_tokens = 0

            await self.events.emit_critique_result(
                project.id, chapter_num,
                loop_result.iterations,
                self._critique_output_to_domain(loop_result),
            )

            # Save chapter
            chapter = Chapter(
                number=chapter_num,
                content=loop_result.final_prose,
                word_count=loop_result.word_count,
                blueprint=blueprint,
                final_score=loop_result.final_score,
                status="completed",
            )
            await self.storage.save_chapter(project.id, chapter)

            # Update story bible with new chapter content
            await self._update_story_bible_from_chapter(
                context, consistency_agent, agent_bible,
                chapter_num, loop_result.final_prose,
            )

        # Persist the updated story bible
        story_bible.entries = []
        for name, char in agent_bible.data.characters.items():
            story_bible.add_entry(
                _bible_entry("character", name, char.description, char.first_appearance),
            )
        for name, loc in agent_bible.data.locations.items():
            story_bible.add_entry(
                _bible_entry("location", name, loc.description, loc.first_mentioned),
            )
        story_bible.timeline = [
            {"chapter": e.chapter, "description": e.description}
            for e in agent_bible.data.timeline
        ]
        story_bible.last_updated = datetime.utcnow()
        await self.storage.save_story_bible(story_bible)

        # Record prose phase completion
        run.total_input_tokens += total_usage.input_tokens
        run.total_output_tokens += total_usage.output_tokens
        run.estimated_cost_usd = TokenUsage(
            run.total_input_tokens, run.total_output_tokens,
        ).estimated_cost_usd
        await self.storage.save_pipeline_run(run)

    async def _run_final_consistency_check(
        self, context, project, config, run,
    ) -> None:
        """Phase 7 — final consistency pass across all chapters."""
        run.current_phase = PhaseType.CONSISTENCY_CHECK
        await self.events.emit_phase_started(project.id, PhaseType.CONSISTENCY_CHECK.value)

        story_bible = await self.storage.get_story_bible(project.id)
        bible_text = story_bible.to_context_string() if story_bible else ""

        # Gather all chapter texts
        chapters = await self.storage.list_chapters(project.id)
        all_prose = "\n\n---\n\n".join(
            f"## Chapter {ch.number}\n{ch.content or ''}" for ch in chapters
        )

        # Use the consistency agent for a final sweep
        agent = self._get_agent(PHASE_MAP[PhaseType.CONSISTENCY_CHECK])
        input_data = ConsistencyInput(
            chapter_index=0,  # 0 = full-book check
            chapter_prose=all_prose[:15000],  # Truncate to fit context
            story_bible_json=json.dumps({"summary": bible_text}),
        )

        result = await agent.execute(input_data, context)

        output_dict = self._to_serialisable(result.output) if result.success else {"error": result.error}
        usage = TokenUsage(result.input_tokens, result.output_tokens)

        await self._record_phase(run, project.id, PhaseType.CONSISTENCY_CHECK, output_dict, usage)

    # ------------------------------------------------------------------
    # Agent execution helper
    # ------------------------------------------------------------------

    async def _execute_agent(
        self,
        phase_type: PhaseType,
        input_data,
        context: AgentContext,
        run: PipelineRun,
    ) -> tuple:
        """
        Execute a registered agent for a phase.

        Returns (output, TokenUsage).
        Also records the phase result on the run.
        """
        run.current_phase = phase_type
        await self.events.emit_phase_started(context.project_id, phase_type.value)

        agent_phase = PHASE_MAP[phase_type]
        agent = self._get_agent(agent_phase)

        result = await agent.execute(input_data, context)

        if not result.success:
            raise RuntimeError(f"Phase {phase_type.value} failed: {result.error}")

        usage = TokenUsage(result.input_tokens, result.output_tokens)
        output_dict = self._to_serialisable(result.output)

        await self._record_phase(run, context.project_id, phase_type, output_dict, usage)

        return result.output, usage

    # ------------------------------------------------------------------
    # Phase recording & approval
    # ------------------------------------------------------------------

    async def _record_phase(
        self,
        run: PipelineRun,
        project_id: int,
        phase_type: PhaseType,
        output: Dict[str, Any],
        usage: TokenUsage,
    ) -> PipelineRun:
        """Persist a completed phase result and update the run."""
        phase_result = PhaseResult(
            phase=phase_type,
            status=PhaseStatus.COMPLETED.value,
            output=output,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )

        self._track_tokens(run, phase_result)
        run.phases.append(phase_result)

        await self.storage.save_phase_result(project_id, phase_result)
        await self.events.emit_phase_completed(project_id, phase_result)
        await self.storage.save_pipeline_run(run)

        return run

    async def _approval_gate(
        self,
        phase_type: PhaseType,
        output: Dict[str, Any],
        config: GenerationConfig,
        run: PipelineRun,
        project_id: int,
    ) -> None:
        """Pause execution if the phase requires user approval."""
        if config.auto_approve:
            return
        if phase_type not in APPROVAL_PHASES:
            return

        run.status = PipelineStatus.AWAITING_APPROVAL.value
        await self.storage.save_pipeline_run(run)
        await self.events.emit_approval_required(project_id, phase_type.value, output)
        raise PipelinePausedError(f"Awaiting approval for {phase_type.value}")

    # ------------------------------------------------------------------
    # Story bible helpers
    # ------------------------------------------------------------------

    async def _update_story_bible_from_chapter(
        self,
        context: AgentContext,
        consistency_agent,
        agent_bible: AgentStoryBible,
        chapter_num: int,
        prose: str,
    ) -> None:
        """Run consistency agent on a chapter and merge updates into the bible."""
        input_data = ConsistencyInput(
            chapter_index=chapter_num,
            chapter_prose=prose[:12000],  # Truncate very long chapters
            story_bible_json=agent_bible.to_json(),
        )

        result = await consistency_agent.execute(input_data, context)

        if result.success and result.output:
            updates = result.output.updates if hasattr(result.output, "updates") else []
            agent_bible.apply_updates(updates)

    async def _build_previous_context(
        self, project_id: int, current_chapter: int,
    ) -> str:
        """Build a summary of previous chapters for context."""
        if current_chapter <= 1:
            return ""

        parts = []
        # Include last 2 chapters' endings (for continuity)
        for ch_num in range(max(1, current_chapter - 2), current_chapter):
            chapter = await self.storage.get_chapter(project_id, ch_num)
            if chapter and chapter.content:
                # Take last ~500 chars as a continuity bridge
                ending = chapter.content[-500:]
                parts.append(f"Chapter {ch_num} (ending): ...{ending}")

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    def _critique_output_to_domain(self, loop_result):
        """Convert ProseLoopResult critique data to domain CritiqueResult."""
        from ..domain.values import CritiqueScore, CritiqueResult

        if not loop_result.critique_history:
            return CritiqueResult(
                scores=(), overall_score=loop_result.final_score,
                passes_threshold=loop_result.final_score >= 7.0,
            )

        last_critique = loop_result.critique_history[-1]
        scores = [
            CritiqueScore(
                category=s.category, score=s.score,
                feedback=s.feedback, weight=1.0,
            )
            for s in last_critique.scores
        ]
        return CritiqueResult.from_scores(scores)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _bible_entry(category, name, description, first_appearance):
    """Create a StoryBibleEntry without importing at module level."""
    from ..domain import StoryBibleEntry
    return StoryBibleEntry(
        category=category,
        name=name,
        description=description,
        first_appearance=first_appearance,
    )
