"""Story Architect Agent - designs story structure."""

import json
import time
from typing import Any

from ..base import BaseAgent, AgentContext, AgentResult, AgentPhase
from ..registry import AgentRegistry
from .schema import (
    StoryArchitectureInput,
    StoryArchitectureOutput,
    ActBreakdown,
    TurningPoint,
    ChapterPacing
)


@AgentRegistry.register(AgentPhase.STORY_ARCHITECTURE)
class StoryArchitectAgent(BaseAgent[StoryArchitectureInput, StoryArchitectureOutput]):
    """
    Phase 4: Architect the story's structure.

    Designs the story's acts, turning points, and overall narrative arc.
    """

    phase = AgentPhase.STORY_ARCHITECTURE
    name = "Story Architect"
    description = "Design story structure, acts, and narrative arc"
    requires_approval = True

    async def execute(
        self,
        input_data: StoryArchitectureInput,
        context: AgentContext
    ) -> AgentResult[StoryArchitectureOutput]:
        """Execute story architecture design."""
        start_time = time.time()

        try:
            author_name = context.author_profile.get("name", "Unknown Author")

            system_prompt, user_prompt = self.prompts.render(
                "story_architecture",
                author_name=author_name,
                story_thesis=input_data.story_thesis,
                characters=input_data.characters,
                structure_type=input_data.structure_type,
                chapter_count=input_data.chapter_count
            )

            response = await self.llm.generate(
                prompt=user_prompt,
                system=system_prompt,
                max_tokens=3000
            )

            context.add_token_usage(response.input_tokens, response.output_tokens)

            output = await self._parse_architecture(
                response.text, input_data.chapter_count, context
            )

            execution_time_ms = int((time.time() - start_time) * 1000)

            return AgentResult.success_result(
                output=output,
                reasoning=f"Architected {len(output.acts)} acts across {input_data.chapter_count} chapters",
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                execution_time_ms=execution_time_ms,
                requires_approval=True
            )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            return AgentResult.failure_result(
                error=f"Story architecture failed: {str(e)}",
                execution_time_ms=execution_time_ms
            )

    async def _parse_architecture(
        self,
        raw_text: str,
        chapter_count: int,
        context: AgentContext
    ) -> StoryArchitectureOutput:
        """Parse architecture into structured output."""

        extraction_prompt = f"""
Extract story architecture from this text into JSON:

{raw_text}

Return ONLY valid JSON:
{{
    "acts": [
        {{
            "act_number": 1,
            "purpose": "...",
            "key_events": ["event1", "event2"],
            "character_state": "...",
            "tension_level": "building",
            "chapters": [1, 2, 3]
        }}
    ],
    "turning_points": [
        {{"name": "Inciting Incident", "description": "...", "chapter": 1}}
    ],
    "recurring_elements": ["element1"],
    "parallel_structures": ["structure1"],
    "subplots": ["subplot1"],
    "chapter_pacing": [
        {{"chapter": 1, "pacing": "medium", "tension": 3, "focus": "..."}}
    ]
}}

Generate chapter_pacing for all {chapter_count} chapters.
"""

        response = await self.llm.generate(
            prompt=extraction_prompt,
            system="Extract structured data. Return only valid JSON.",
            max_tokens=2000
        )

        context.add_token_usage(response.input_tokens, response.output_tokens)

        try:
            text = response.text.strip()
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]

            data = json.loads(text.strip())

            return StoryArchitectureOutput(
                acts=[ActBreakdown(**act) for act in data.get("acts", [])],
                turning_points=[
                    TurningPoint(**tp) for tp in data.get("turning_points", [])
                ],
                recurring_elements=data.get("recurring_elements", []),
                parallel_structures=data.get("parallel_structures", []),
                subplots=data.get("subplots", []),
                chapter_pacing=[
                    ChapterPacing(**cp) for cp in data.get("chapter_pacing", [])
                ],
                raw_architecture=raw_text
            )
        except (json.JSONDecodeError, KeyError) as e:
            raise ValueError(f"Failed to parse architecture: {e}")
