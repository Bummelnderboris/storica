"""Topic Explorer Agent - explores story spark through author's lens."""

import json
import time
from typing import Any

from ..base import BaseAgent, AgentContext, AgentResult, AgentPhase
from ..registry import AgentRegistry
from .schema import (
    TopicExplorationInput,
    TopicExplorationOutput,
    ThematicDepth,
    PhilosophicalAngle
)


@AgentRegistry.register(AgentPhase.TOPIC_EXPLORATION)
class TopicExplorerAgent(BaseAgent[TopicExplorationInput, TopicExplorationOutput]):
    """
    Phase 1: Explore the story spark through the author's philosophical lens.

    This agent takes the initial story spark and genre, then explores it
    deeply through the selected author's worldview, finding themes,
    ironies, and unique angles.
    """

    phase = AgentPhase.TOPIC_EXPLORATION
    name = "Topic Explorer"
    description = "Explore story spark through author's philosophical lens"
    requires_approval = True  # User should approve thematic direction

    async def execute(
        self,
        input_data: TopicExplorationInput,
        context: AgentContext
    ) -> AgentResult[TopicExplorationOutput]:
        """Execute topic exploration."""
        start_time = time.time()

        try:
            # Get author profile from context
            author_name = context.author_profile.get("name", "Unknown Author")
            author_philosophy = context.author_profile.get("philosophy", "")

            # Build prompt from template
            system_prompt, user_prompt = self.prompts.render(
                "topic_exploration",
                author_name=author_name,
                author_philosophy=author_philosophy,
                story_spark=input_data.story_spark,
                genre=input_data.genre
            )

            # Generate exploration
            response = await self.llm.generate(
                prompt=user_prompt,
                system=system_prompt,
                max_tokens=2000
            )

            context.add_token_usage(response.input_tokens, response.output_tokens)

            # Parse the response into structured output
            output = await self._parse_exploration(response.text, context)

            execution_time_ms = int((time.time() - start_time) * 1000)

            return AgentResult.success_result(
                output=output,
                reasoning=f"Explored '{input_data.story_spark}' through {author_name}'s lens",
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                execution_time_ms=execution_time_ms,
                requires_approval=True
            )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            return AgentResult.failure_result(
                error=f"Topic exploration failed: {str(e)}",
                execution_time_ms=execution_time_ms
            )

    async def _parse_exploration(
        self,
        raw_text: str,
        context: AgentContext
    ) -> TopicExplorationOutput:
        """Parse raw exploration text into structured output."""

        # Use LLM to extract structured data
        extraction_prompt = f"""
Extract the following from this topic exploration into JSON:

{raw_text}

Return ONLY valid JSON with this structure:
{{
    "thematic_depths": [
        {{"theme": "...", "interpretation": "...", "author_angle": "..."}}
    ],
    "philosophical_angles": [
        {{"question": "...", "exploration_direction": "..."}}
    ],
    "ironic_possibilities": ["...", "..."],
    "central_tension": "...",
    "unique_angle": "..."
}}
"""

        response = await self.llm.generate(
            prompt=extraction_prompt,
            system="You extract structured data from text. Return only valid JSON.",
            max_tokens=1500
        )

        context.add_token_usage(response.input_tokens, response.output_tokens)

        # Parse JSON from response
        try:
            # Find JSON in response
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]

            data = json.loads(text.strip())

            return TopicExplorationOutput(
                thematic_depths=[
                    ThematicDepth(**td) for td in data.get("thematic_depths", [])
                ],
                philosophical_angles=[
                    PhilosophicalAngle(**pa) for pa in data.get("philosophical_angles", [])
                ],
                ironic_possibilities=data.get("ironic_possibilities", []),
                central_tension=data.get("central_tension", ""),
                unique_angle=data.get("unique_angle", ""),
                raw_exploration=raw_text
            )
        except json.JSONDecodeError:
            # Fallback: return raw text with minimal structure
            return TopicExplorationOutput(
                thematic_depths=[
                    ThematicDepth(
                        theme="See raw exploration",
                        interpretation="",
                        author_angle=""
                    )
                ],
                philosophical_angles=[
                    PhilosophicalAngle(
                        question="See raw exploration",
                        exploration_direction=""
                    )
                ],
                ironic_possibilities=[],
                central_tension="See raw exploration for details",
                unique_angle="See raw exploration for details",
                raw_exploration=raw_text
            )
