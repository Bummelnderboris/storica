"""Pipeline orchestrator - coordinates the multi-agent pipeline."""

import json
from typing import Any, Callable, Optional
from dataclasses import dataclass

from .state import PipelineState, PipelineStatus
from .gates import ApprovalGate, ApprovalDecision

from ..agents.base import AgentContext, AgentPhase
from ..agents.registry import AgentRegistry
from ..agents.phase0_author import AuthorMindLoaderAgent
from ..agents.phase0_author.schema import AuthorMindInput
from ..agents.phase1_topic import TopicExplorerAgent
from ..agents.phase1_topic.schema import TopicExplorationInput
from ..agents.phase2_thesis import ThesisDeveloperAgent
from ..agents.phase2_thesis.schema import ThesisDevelopmentInput
from ..agents.phase3_character import CharacterDeriverAgent
from ..agents.phase3_character.schema import CharacterDerivationInput
from ..agents.phase4_architecture import StoryArchitectAgent
from ..agents.phase4_architecture.schema import StoryArchitectureInput
from ..agents.phase5_blueprint import BlueprintPlannerAgent
from ..agents.phase5_blueprint.schema import BlueprintInput
from ..agents.phase6_prose import ProseGenerationLoop, LoopCallbacks
from ..agents.phase6_prose.schema import ProseInput
from ..agents.phase7_consistency import ConsistencyGuardianAgent
from ..agents.phase7_consistency.schema import ConsistencyInput
from ..agents.phase7_consistency.story_bible import StoryBible


@dataclass
class PipelineCallbacks:
    """Callbacks for pipeline events."""
    on_phase_start: Optional[Callable[[str], None]] = None
    on_phase_complete: Optional[Callable[[str, dict], None]] = None
    on_approval_required: Optional[Callable[[str, dict], None]] = None
    on_chapter_start: Optional[Callable[[int], None]] = None
    on_chapter_complete: Optional[Callable[[int], None]] = None
    on_pipeline_complete: Optional[Callable[[dict], None]] = None
    on_error: Optional[Callable[[str, str], None]] = None


class PipelineOrchestrator:
    """
    Orchestrates the complete novel generation pipeline.

    Coordinates all agents through the pipeline phases,
    managing state, approvals, and chapter generation.
    """

    def __init__(
        self,
        llm_service: Any,
        prompt_engine: Any,
        author_loader: Any
    ):
        self.llm = llm_service
        self.prompts = prompt_engine
        self.authors = author_loader
        self.approval_gate = ApprovalGate()

    async def run_pipeline(
        self,
        project_id: int,
        author_id: str,
        story_dna: dict,
        callbacks: Optional[PipelineCallbacks] = None,
        auto_approve: bool = False
    ) -> PipelineState:
        """
        Run the complete pipeline for a project.

        Args:
            project_id: Project ID
            author_id: Author profile ID
            story_dna: Story DNA from quiz
            callbacks: Optional event callbacks
            auto_approve: If True, skip approval gates

        Returns:
            Final pipeline state
        """
        callbacks = callbacks or PipelineCallbacks()

        # Initialize state
        state = PipelineState(project_id=project_id)
        state.author_id = author_id
        state.total_chapters = story_dna.get("structure", {}).get("chapter_count", 12)
        state.start()

        # Create agent context
        context = AgentContext(
            project_id=project_id,
            author_id=author_id,
            story_dna=story_dna,
            max_iterations=3
        )

        try:
            # Phase 0: Load Author
            await self._run_phase_0(state, context, callbacks)

            # Phase 1: Topic Exploration
            await self._run_phase_1(state, context, story_dna, callbacks, auto_approve)

            # Phase 2: Thesis Development
            await self._run_phase_2(state, context, callbacks, auto_approve)

            # Phase 3: Character Derivation
            await self._run_phase_3(state, context, callbacks, auto_approve)

            # Phase 4: Story Architecture
            await self._run_phase_4(state, context, story_dna, callbacks, auto_approve)

            # Phases 5-7: Chapter Loop
            await self._run_chapter_loop(state, context, callbacks, auto_approve)

            state.complete()

            if callbacks.on_pipeline_complete:
                callbacks.on_pipeline_complete(state.to_dict())

        except Exception as e:
            state.fail(str(e))
            if callbacks.on_error:
                callbacks.on_error(state.current_phase or "unknown", str(e))

        return state

    async def _run_phase_0(
        self,
        state: PipelineState,
        context: AgentContext,
        callbacks: PipelineCallbacks
    ) -> None:
        """Phase 0: Load author profile."""
        phase_name = "author_loading"
        state.start_phase(phase_name)

        if callbacks.on_phase_start:
            callbacks.on_phase_start(phase_name)

        agent = AgentRegistry.get_agent(
            AgentPhase.AUTHOR_LOADING,
            self.llm,
            self.prompts
        )

        input_data = AuthorMindInput(author_id=context.author_id)
        result = await agent.execute(input_data, context)

        if not result.success:
            raise RuntimeError(f"Author loading failed: {result.error}")

        state.author_language = result.output.primary_language
        state.complete_phase(
            phase_name,
            result.output.model_dump(),
            result.input_tokens,
            result.output_tokens,
            result.execution_time_ms
        )

        if callbacks.on_phase_complete:
            callbacks.on_phase_complete(phase_name, result.output.model_dump())

    async def _run_phase_1(
        self,
        state: PipelineState,
        context: AgentContext,
        story_dna: dict,
        callbacks: PipelineCallbacks,
        auto_approve: bool
    ) -> None:
        """Phase 1: Topic Exploration."""
        phase_name = "topic_exploration"
        state.start_phase(phase_name)

        if callbacks.on_phase_start:
            callbacks.on_phase_start(phase_name)

        agent = AgentRegistry.get_agent(
            AgentPhase.TOPIC_EXPLORATION,
            self.llm,
            self.prompts
        )

        spark = story_dna.get("spark", {})
        genre = story_dna.get("genre", {})

        input_data = TopicExplorationInput(
            story_spark=spark.get("description", ""),
            genre=genre.get("primary_genre", ""),
            subgenres=genre.get("subgenres", [])
        )

        result = await agent.execute(input_data, context)

        if not result.success:
            raise RuntimeError(f"Topic exploration failed: {result.error}")

        # Handle approval if needed
        if result.requires_approval and not auto_approve:
            approved = await self._wait_for_approval(
                state, phase_name, result.output.model_dump(), callbacks
            )
            if not approved:
                raise RuntimeError("Topic exploration rejected")

        state.topic_exploration = result.output.model_dump()
        context.previous_outputs["topic_exploration"] = state.topic_exploration

        state.complete_phase(
            phase_name,
            result.output.model_dump(),
            result.input_tokens,
            result.output_tokens,
            result.execution_time_ms
        )

        if callbacks.on_phase_complete:
            callbacks.on_phase_complete(phase_name, result.output.model_dump())

    async def _run_phase_2(
        self,
        state: PipelineState,
        context: AgentContext,
        callbacks: PipelineCallbacks,
        auto_approve: bool
    ) -> None:
        """Phase 2: Thesis Development."""
        phase_name = "thesis_development"
        state.start_phase(phase_name)

        if callbacks.on_phase_start:
            callbacks.on_phase_start(phase_name)

        agent = AgentRegistry.get_agent(
            AgentPhase.THESIS_DEVELOPMENT,
            self.llm,
            self.prompts
        )

        topic_exp = state.topic_exploration or {}

        input_data = ThesisDevelopmentInput(
            topic_exploration=topic_exp.get("raw_exploration", str(topic_exp)),
            story_dna_summary=json.dumps(context.story_dna)
        )

        result = await agent.execute(input_data, context)

        if not result.success:
            raise RuntimeError(f"Thesis development failed: {result.error}")

        if result.requires_approval and not auto_approve:
            approved = await self._wait_for_approval(
                state, phase_name, result.output.model_dump(), callbacks
            )
            if not approved:
                raise RuntimeError("Thesis rejected")

        state.story_thesis = result.output.model_dump()
        context.previous_outputs["thesis"] = state.story_thesis

        state.complete_phase(
            phase_name,
            result.output.model_dump(),
            result.input_tokens,
            result.output_tokens,
            result.execution_time_ms
        )

        if callbacks.on_phase_complete:
            callbacks.on_phase_complete(phase_name, result.output.model_dump())

    async def _run_phase_3(
        self,
        state: PipelineState,
        context: AgentContext,
        callbacks: PipelineCallbacks,
        auto_approve: bool
    ) -> None:
        """Phase 3: Character Derivation."""
        phase_name = "character_derivation"
        state.start_phase(phase_name)

        if callbacks.on_phase_start:
            callbacks.on_phase_start(phase_name)

        agent = AgentRegistry.get_agent(
            AgentPhase.CHARACTER_DERIVATION,
            self.llm,
            self.prompts
        )

        thesis = state.story_thesis or {}
        char_dna = context.story_dna.get("characters", {})

        input_data = CharacterDerivationInput(
            story_thesis=thesis.get("central_thesis", str(thesis)),
            story_dna_characters=json.dumps(char_dna),
            author_character_patterns=context.author_profile.get("character_patterns", "")
        )

        result = await agent.execute(input_data, context)

        if not result.success:
            raise RuntimeError(f"Character derivation failed: {result.error}")

        if result.requires_approval and not auto_approve:
            approved = await self._wait_for_approval(
                state, phase_name, result.output.model_dump(), callbacks
            )
            if not approved:
                raise RuntimeError("Characters rejected")

        state.characters = result.output.model_dump()
        context.previous_outputs["characters"] = state.characters

        state.complete_phase(
            phase_name,
            result.output.model_dump(),
            result.input_tokens,
            result.output_tokens,
            result.execution_time_ms
        )

        if callbacks.on_phase_complete:
            callbacks.on_phase_complete(phase_name, result.output.model_dump())

    async def _run_phase_4(
        self,
        state: PipelineState,
        context: AgentContext,
        story_dna: dict,
        callbacks: PipelineCallbacks,
        auto_approve: bool
    ) -> None:
        """Phase 4: Story Architecture."""
        phase_name = "story_architecture"
        state.start_phase(phase_name)

        if callbacks.on_phase_start:
            callbacks.on_phase_start(phase_name)

        agent = AgentRegistry.get_agent(
            AgentPhase.STORY_ARCHITECTURE,
            self.llm,
            self.prompts
        )

        thesis = state.story_thesis or {}
        chars = state.characters or {}
        structure = story_dna.get("structure", {})

        input_data = StoryArchitectureInput(
            story_thesis=thesis.get("central_thesis", str(thesis)),
            characters=json.dumps(chars),
            structure_type=structure.get("structure_type", "three_act"),
            chapter_count=structure.get("chapter_count", 12)
        )

        result = await agent.execute(input_data, context)

        if not result.success:
            raise RuntimeError(f"Story architecture failed: {result.error}")

        if result.requires_approval and not auto_approve:
            approved = await self._wait_for_approval(
                state, phase_name, result.output.model_dump(), callbacks
            )
            if not approved:
                raise RuntimeError("Architecture rejected")

        state.story_architecture = result.output.model_dump()
        context.previous_outputs["architecture"] = state.story_architecture

        state.complete_phase(
            phase_name,
            result.output.model_dump(),
            result.input_tokens,
            result.output_tokens,
            result.execution_time_ms
        )

        if callbacks.on_phase_complete:
            callbacks.on_phase_complete(phase_name, result.output.model_dump())

    async def _run_chapter_loop(
        self,
        state: PipelineState,
        context: AgentContext,
        callbacks: PipelineCallbacks,
        auto_approve: bool
    ) -> None:
        """Run phases 5-7 for each chapter."""
        story_bible = StoryBible()

        for chapter_idx in range(1, state.total_chapters + 1):
            state.current_chapter = chapter_idx

            if callbacks.on_chapter_start:
                callbacks.on_chapter_start(chapter_idx)

            # Get chapter purpose from architecture
            arch = state.story_architecture or {}
            pacing = arch.get("chapter_pacing", [])
            chapter_pacing = next(
                (p for p in pacing if p.get("chapter") == chapter_idx),
                {"focus": f"Chapter {chapter_idx}", "pacing": "medium"}
            )

            # Phase 5: Blueprint
            blueprint = await self._run_blueprint(
                state, context, chapter_idx, chapter_pacing, story_bible
            )

            # Phase 6: Prose Generation
            prose_result = await self._run_prose_generation(
                state, context, chapter_idx, blueprint, story_bible, callbacks
            )

            # Phase 7: Consistency Check
            await self._run_consistency_check(
                state, context, chapter_idx, prose_result, story_bible
            )

            state.chapter_outputs[chapter_idx] = {
                "blueprint": blueprint,
                "prose": prose_result,
                "story_bible": story_bible.to_json()
            }

            if callbacks.on_chapter_complete:
                callbacks.on_chapter_complete(chapter_idx)

        state.story_bible = json.loads(story_bible.to_json())

    async def _run_blueprint(
        self,
        state: PipelineState,
        context: AgentContext,
        chapter_idx: int,
        chapter_pacing: dict,
        story_bible: StoryBible
    ) -> dict:
        """Run Phase 5 for a chapter."""
        agent = AgentRegistry.get_agent(
            AgentPhase.CHAPTER_BLUEPRINTS,
            self.llm,
            self.prompts
        )

        prev_summary = ""
        if chapter_idx > 1 and (chapter_idx - 1) in state.chapter_outputs:
            prev = state.chapter_outputs[chapter_idx - 1]
            prev_summary = f"Previous chapter: {prev.get('prose', {}).get('word_count', 0)} words"

        input_data = BlueprintInput(
            chapter_index=chapter_idx,
            chapter_purpose=chapter_pacing.get("focus", ""),
            story_architecture=json.dumps(state.story_architecture),
            characters=json.dumps(state.characters),
            previous_chapter_summary=prev_summary,
            story_bible=story_bible.to_prompt_summary()
        )

        result = await agent.execute(input_data, context)

        if not result.success:
            raise RuntimeError(f"Blueprint failed: {result.error}")

        return result.output.model_dump()

    async def _run_prose_generation(
        self,
        state: PipelineState,
        context: AgentContext,
        chapter_idx: int,
        blueprint: dict,
        story_bible: StoryBible,
        callbacks: PipelineCallbacks
    ) -> dict:
        """Run Phase 6 prose generation loop."""
        prose_loop = ProseGenerationLoop(
            self.llm, self.prompts, max_iterations=3
        )

        input_data = ProseInput(
            chapter_blueprint=blueprint.get("raw_blueprint", json.dumps(blueprint)),
            story_bible=story_bible.to_prompt_summary(),
            author_style_guide=context.author_profile.get("style_guide", ""),
            author_language=context.author_profile.get("language", "en")
        )

        result = await prose_loop.run(input_data, context)

        return {
            "prose": result.final_prose,
            "word_count": result.word_count,
            "iterations": result.iterations,
            "final_score": result.final_score
        }

    async def _run_consistency_check(
        self,
        state: PipelineState,
        context: AgentContext,
        chapter_idx: int,
        prose_result: dict,
        story_bible: StoryBible
    ) -> dict:
        """Run Phase 7 consistency check."""
        agent = AgentRegistry.get_agent(
            AgentPhase.CONSISTENCY_CHECK,
            self.llm,
            self.prompts
        )

        input_data = ConsistencyInput(
            chapter_index=chapter_idx,
            chapter_prose=prose_result.get("prose", ""),
            story_bible_json=story_bible.to_json()
        )

        result = await agent.execute(input_data, context)

        if result.success:
            # Apply updates to story bible
            story_bible.apply_updates(result.output.updates)

        return result.output.model_dump() if result.success else {}

    async def _wait_for_approval(
        self,
        state: PipelineState,
        phase_name: str,
        output: dict,
        callbacks: PipelineCallbacks
    ) -> bool:
        """Wait for user approval at a phase gate."""
        state.await_approval(phase_name)

        gate_id = self.approval_gate.create_gate(
            phase_name, state.project_id, output
        )

        if callbacks.on_approval_required:
            callbacks.on_approval_required(phase_name, output)

        request = await self.approval_gate.wait_for_approval(gate_id)

        self.approval_gate.cleanup(gate_id)

        if request.decision == ApprovalDecision.APPROVED:
            state.approve_phase(phase_name)
            return True
        else:
            state.reject_phase(
                phase_name,
                request.rejection_reason or "Rejected by user"
            )
            return False

    def approve_phase(self, project_id: int, phase_name: str) -> bool:
        """Approve a pending phase."""
        for request in self.approval_gate.get_pending(project_id):
            if request.phase_name == phase_name:
                return self.approval_gate.approve(request.gate_id)
        return False

    def reject_phase(self, project_id: int, phase_name: str, reason: str) -> bool:
        """Reject a pending phase."""
        for request in self.approval_gate.get_pending(project_id):
            if request.phase_name == phase_name:
                return self.approval_gate.reject(request.gate_id, reason)
        return False
