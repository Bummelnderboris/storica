"""Prose Writer Agent - generates chapter prose."""

import time
from typing import Any, Callable, Optional

from ..base import StreamingAgent, AgentContext, AgentResult, AgentPhase
from .schema import ProseInput, ReasoningOutput, ProseOutput


class ProseWriterAgent(StreamingAgent[ProseInput, ProseOutput]):
    """
    Generates chapter prose in the author's voice.

    Supports streaming output for real-time feedback.
    Uses opus model for higher quality prose.
    """

    phase = AgentPhase.PROSE_GENERATION
    name = "Prose Writer"
    description = "Generate chapter prose in author's voice"
    requires_approval = True

    async def execute(
        self,
        input_data: ProseInput,
        context: AgentContext,
        reasoning: Optional[ReasoningOutput] = None
    ) -> AgentResult[ProseOutput]:
        """Execute prose generation (non-streaming)."""
        start_time = time.time()

        try:
            author_name = context.author_profile.get("name", "Unknown Author")
            reasoning_text = ""
            if reasoning:
                reasoning_text = f"""
Voice: {reasoning.voice_calibration}
Opening: {reasoning.opening_strategy}
Key Moments: {reasoning.key_moments}
"""

            system_prompt, user_prompt = self.prompts.render(
                "prose_writing",
                author_name=author_name,
                author_language=input_data.author_language,
                author_style_guide=input_data.author_style_guide,
                chapter_blueprint=input_data.chapter_blueprint,
                reasoning=reasoning_text,
                story_bible=input_data.story_bible
            )

            # Use opus model for prose generation
            response = await self.llm.generate(
                prompt=user_prompt,
                system=system_prompt,
                max_tokens=8000,
                model="opus"  # Higher quality for prose
            )

            context.add_token_usage(response.input_tokens, response.output_tokens)

            prose = response.text.strip()
            word_count = len(prose.split())

            output = ProseOutput(prose=prose, word_count=word_count)

            execution_time_ms = int((time.time() - start_time) * 1000)

            return AgentResult.success_result(
                output=output,
                reasoning=f"Generated {word_count} words",
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                execution_time_ms=execution_time_ms,
                requires_approval=True
            )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            return AgentResult.failure_result(
                error=f"Prose generation failed: {str(e)}",
                execution_time_ms=execution_time_ms
            )

    async def execute_streaming(
        self,
        input_data: ProseInput,
        context: AgentContext,
        on_chunk: Callable[[str], None],
        reasoning: Optional[ReasoningOutput] = None
    ) -> AgentResult[ProseOutput]:
        """Execute prose generation with streaming output."""
        start_time = time.time()
        collected_prose = []

        try:
            author_name = context.author_profile.get("name", "Unknown Author")
            reasoning_text = ""
            if reasoning:
                reasoning_text = f"""
Voice: {reasoning.voice_calibration}
Opening: {reasoning.opening_strategy}
Key Moments: {reasoning.key_moments}
"""

            system_prompt, user_prompt = self.prompts.render(
                "prose_writing",
                author_name=author_name,
                author_language=input_data.author_language,
                author_style_guide=input_data.author_style_guide,
                chapter_blueprint=input_data.chapter_blueprint,
                reasoning=reasoning_text,
                story_bible=input_data.story_bible
            )

            # Stream the response
            async for chunk in self.llm.generate_stream(
                prompt=user_prompt,
                system=system_prompt,
                max_tokens=8000,
                model="opus"
            ):
                collected_prose.append(chunk.text)
                on_chunk(chunk.text)

            prose = "".join(collected_prose).strip()
            word_count = len(prose.split())

            output = ProseOutput(prose=prose, word_count=word_count)

            execution_time_ms = int((time.time() - start_time) * 1000)

            return AgentResult.success_result(
                output=output,
                reasoning=f"Generated {word_count} words (streamed)",
                execution_time_ms=execution_time_ms,
                requires_approval=True
            )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            return AgentResult.failure_result(
                error=f"Streaming prose generation failed: {str(e)}",
                execution_time_ms=execution_time_ms
            )
