"""Prose Generation Loop - orchestrates the multi-agent prose generation."""

import time
from typing import Any, Callable, Optional
from dataclasses import dataclass

from ..base import AgentContext
from .reasoner import ProseReasonerAgent
from .writer import ProseWriterAgent
from .critic import ProseCriticAgent, CritiqueInput
from .reviser import ProseReviserAgent, RevisionInput
from .schema import ProseInput, ProseLoopResult, CritiqueOutput


@dataclass
class LoopCallbacks:
    """Callbacks for loop events."""
    on_reasoning_start: Optional[Callable[[], None]] = None
    on_reasoning_complete: Optional[Callable[[str], None]] = None
    on_writing_start: Optional[Callable[[int], None]] = None  # iteration
    on_writing_chunk: Optional[Callable[[str], None]] = None
    on_writing_complete: Optional[Callable[[int], None]] = None  # word count
    on_critique_start: Optional[Callable[[int], None]] = None
    on_critique_complete: Optional[Callable[[float, bool], None]] = None  # score, passes
    on_revision_start: Optional[Callable[[int], None]] = None
    on_revision_complete: Optional[Callable[[int], None]] = None  # word count
    on_loop_complete: Optional[Callable[[int, float], None]] = None  # iterations, final_score


class ProseGenerationLoop:
    """
    Orchestrates the prose generation multi-agent loop.

    Flow: Reasoner -> Writer -> Critic -> (if not passing) Reviser -> Critic -> ...

    The loop continues until:
    - The critique passes the threshold, or
    - Max iterations is reached
    """

    def __init__(
        self,
        llm_service: Any,
        prompt_engine: Any,
        max_iterations: int = 3,
        passing_threshold: float = 7.0
    ):
        self.max_iterations = max_iterations
        self.passing_threshold = passing_threshold

        # Initialize agents
        self.reasoner = ProseReasonerAgent(llm_service, prompt_engine)
        self.writer = ProseWriterAgent(llm_service, prompt_engine)
        self.critic = ProseCriticAgent(llm_service, prompt_engine)
        self.reviser = ProseReviserAgent(llm_service, prompt_engine)

    async def run(
        self,
        input_data: ProseInput,
        context: AgentContext,
        callbacks: Optional[LoopCallbacks] = None
    ) -> ProseLoopResult:
        """
        Run the prose generation loop.

        Args:
            input_data: Input for prose generation
            context: Pipeline context
            callbacks: Optional callbacks for events

        Returns:
            ProseLoopResult with final prose and metadata
        """
        callbacks = callbacks or LoopCallbacks()
        critique_history: list[CritiqueOutput] = []

        # Phase 1: Reasoning
        if callbacks.on_reasoning_start:
            callbacks.on_reasoning_start()

        reasoning_result = await self.reasoner.execute(input_data, context)

        if not reasoning_result.success:
            raise RuntimeError(f"Reasoning failed: {reasoning_result.error}")

        reasoning = reasoning_result.output

        if callbacks.on_reasoning_complete:
            callbacks.on_reasoning_complete(reasoning.voice_calibration[:200])

        # Phase 2: Initial Writing
        if callbacks.on_writing_start:
            callbacks.on_writing_start(1)

        if callbacks.on_writing_chunk:
            # Use streaming
            write_result = await self.writer.execute_streaming(
                input_data, context, callbacks.on_writing_chunk, reasoning
            )
        else:
            write_result = await self.writer.execute(input_data, context, reasoning)

        if not write_result.success:
            raise RuntimeError(f"Writing failed: {write_result.error}")

        current_prose = write_result.output.prose

        if callbacks.on_writing_complete:
            callbacks.on_writing_complete(write_result.output.word_count)

        # Phase 3: Critique-Revise Loop
        iteration = 1
        final_score = 0.0

        while iteration <= self.max_iterations:
            # Critique
            if callbacks.on_critique_start:
                callbacks.on_critique_start(iteration)

            critique_input = CritiqueInput(
                prose=current_prose,
                chapter_blueprint=input_data.chapter_blueprint,
                author_style_guide=input_data.author_style_guide,
                critique_rubric=context.author_profile.get("critique_rubric", {}),
                story_bible=input_data.story_bible
            )

            critique_result = await self.critic.execute(critique_input, context)

            if not critique_result.success:
                raise RuntimeError(f"Critique failed: {critique_result.error}")

            critique = critique_result.output
            critique_history.append(critique)
            final_score = critique.overall_score

            if callbacks.on_critique_complete:
                callbacks.on_critique_complete(final_score, critique.passes_threshold)

            # Check if we pass
            if critique.passes_threshold:
                break

            # Don't revise on last iteration
            if iteration >= self.max_iterations:
                break

            # Revise
            if callbacks.on_revision_start:
                callbacks.on_revision_start(iteration)

            revision_input = RevisionInput(
                original_prose=current_prose,
                critique=critique,
                author_style_guide=input_data.author_style_guide,
                author_language=input_data.author_language
            )

            revision_result = await self.reviser.execute(revision_input, context)

            if not revision_result.success:
                raise RuntimeError(f"Revision failed: {revision_result.error}")

            current_prose = revision_result.output.revised_prose

            if callbacks.on_revision_complete:
                callbacks.on_revision_complete(revision_result.output.word_count)

            iteration += 1

        if callbacks.on_loop_complete:
            callbacks.on_loop_complete(iteration, final_score)

        return ProseLoopResult(
            final_prose=current_prose,
            word_count=len(current_prose.split()),
            iterations=iteration,
            final_score=final_score,
            critique_history=critique_history
        )
