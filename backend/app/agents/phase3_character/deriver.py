"""Character Deriver Agent - derives characters from thesis."""

import json
import time
from typing import Any

from ..base import BaseAgent, AgentContext, AgentResult, AgentPhase
from ..registry import AgentRegistry
from .schema import (
    CharacterDerivationInput,
    CharacterDerivationOutput,
    Protagonist,
    Antagonist,
    SupportingCharacter
)


@AgentRegistry.register(AgentPhase.CHARACTER_DERIVATION)
class CharacterDeriverAgent(BaseAgent[CharacterDerivationInput, CharacterDerivationOutput]):
    """
    Phase 3: Derive characters from story thesis.

    Creates a cast of characters that serves the story's thesis
    while remaining complex individuals.
    """

    phase = AgentPhase.CHARACTER_DERIVATION
    name = "Character Deriver"
    description = "Derive characters from story thesis and author patterns"
    requires_approval = True

    async def execute(
        self,
        input_data: CharacterDerivationInput,
        context: AgentContext
    ) -> AgentResult[CharacterDerivationOutput]:
        """Execute character derivation."""
        start_time = time.time()

        try:
            author_name = context.author_profile.get("name", "Unknown Author")

            system_prompt, user_prompt = self.prompts.render(
                "character_derivation",
                author_name=author_name,
                story_thesis=input_data.story_thesis,
                character_patterns=input_data.author_character_patterns,
                story_dna=input_data.story_dna_characters
            )

            response = await self.llm.generate(
                prompt=user_prompt,
                system=system_prompt,
                max_tokens=2500
            )

            context.add_token_usage(response.input_tokens, response.output_tokens)

            output = await self._parse_characters(response.text, context)

            execution_time_ms = int((time.time() - start_time) * 1000)

            return AgentResult.success_result(
                output=output,
                reasoning=f"Created protagonist: {output.protagonist.name}",
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                execution_time_ms=execution_time_ms,
                requires_approval=True
            )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            return AgentResult.failure_result(
                error=f"Character derivation failed: {str(e)}",
                execution_time_ms=execution_time_ms
            )

    async def _parse_characters(
        self,
        raw_text: str,
        context: AgentContext
    ) -> CharacterDerivationOutput:
        """Parse character descriptions into structured output."""

        extraction_prompt = f"""
Extract characters from this text into JSON:

{raw_text}

Return ONLY valid JSON:
{{
    "protagonist": {{
        "name": "...",
        "core_want": "...",
        "core_need": "...",
        "fatal_flaw": "...",
        "contradictions": "...",
        "voice": "...",
        "arc": "..."
    }},
    "antagonist": {{
        "nature": "...",
        "motivation": "...",
        "relationship_to_thesis": "...",
        "complexity": "...",
        "name": "..."
    }},
    "supporting_cast": [
        {{
            "name": "...",
            "role": "...",
            "relationship": "...",
            "thematic_purpose": "...",
            "distinctive_trait": "..."
        }}
    ],
    "character_dynamics": "..."
}}
"""

        response = await self.llm.generate(
            prompt=extraction_prompt,
            system="Extract structured data. Return only valid JSON.",
            max_tokens=1500
        )

        context.add_token_usage(response.input_tokens, response.output_tokens)

        try:
            text = response.text.strip()
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]

            data = json.loads(text.strip())

            return CharacterDerivationOutput(
                protagonist=Protagonist(**data["protagonist"]),
                antagonist=Antagonist(**data["antagonist"]),
                supporting_cast=[
                    SupportingCharacter(**sc)
                    for sc in data.get("supporting_cast", [])
                ],
                character_dynamics=data.get("character_dynamics", "")
            )
        except (json.JSONDecodeError, KeyError) as e:
            raise ValueError(f"Failed to parse character data: {e}")
