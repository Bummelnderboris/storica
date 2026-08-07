"""Thesis Developer Agent - develops story's central thesis."""

import json
import time
from typing import Any

from ..base import BaseAgent, AgentContext, AgentResult, AgentPhase
from ..registry import AgentRegistry
from .schema import ThesisDevelopmentInput, ThesisDevelopmentOutput


@AgentRegistry.register(AgentPhase.THESIS_DEVELOPMENT)
class ThesisDeveloperAgent(BaseAgent[ThesisDevelopmentInput, ThesisDevelopmentOutput]):
    """
    Phase 2: Develop the story's central thesis.

    Takes the topic exploration and develops a compelling thesis
    that will guide all narrative decisions.
    """

    phase = AgentPhase.THESIS_DEVELOPMENT
    name = "Thesis Developer"
    description = "Develop the story's central thesis and thematic argument"
    requires_approval = True

    async def execute(
        self,
        input_data: ThesisDevelopmentInput,
        context: AgentContext
    ) -> AgentResult[ThesisDevelopmentOutput]:
        """Execute thesis development."""
        start_time = time.time()

        try:
            author_name = context.author_profile.get("name", "Unknown Author")

            system_prompt, user_prompt = self.prompts.render(
                "thesis_development",
                author_name=author_name,
                topic_exploration=input_data.topic_exploration,
                story_dna=input_data.story_dna_summary
            )

            response = await self.llm.generate(
                prompt=user_prompt,
                system=system_prompt,
                max_tokens=1500
            )

            context.add_token_usage(response.input_tokens, response.output_tokens)

            output = await self._parse_thesis(response.text, context)

            execution_time_ms = int((time.time() - start_time) * 1000)

            return AgentResult.success_result(
                output=output,
                reasoning=f"Developed thesis: {output.central_thesis[:100]}...",
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                execution_time_ms=execution_time_ms,
                requires_approval=True
            )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            return AgentResult.failure_result(
                error=f"Thesis development failed: {str(e)}",
                execution_time_ms=execution_time_ms
            )

    async def _parse_thesis(
        self,
        raw_text: str,
        context: AgentContext
    ) -> ThesisDevelopmentOutput:
        """Parse raw thesis text into structured output."""

        extraction_prompt = f"""
Extract from this thesis development into JSON:

{raw_text}

Return ONLY valid JSON:
{{
    "central_thesis": "One sentence thesis",
    "antithesis": "The opposing view",
    "thematic_questions": ["question1", "question2", "question3"],
    "moral_complexity": "How it avoids moralizing",
    "author_resonance": "Connection to author's work"
}}
"""

        response = await self.llm.generate(
            prompt=extraction_prompt,
            system="Extract structured data. Return only valid JSON.",
            max_tokens=1000
        )

        context.add_token_usage(response.input_tokens, response.output_tokens)

        try:
            text = response.text.strip()
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]

            data = json.loads(text.strip())

            return ThesisDevelopmentOutput(**data)
        except (json.JSONDecodeError, KeyError):
            # Fallback
            return ThesisDevelopmentOutput(
                central_thesis=raw_text[:500],
                antithesis="See full text",
                thematic_questions=["See full text"],
                moral_complexity="See full text",
                author_resonance="See full text"
            )
