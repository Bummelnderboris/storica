"""Prose Reasoner Agent - plans approach before writing."""

import json
import time
from typing import Any

from ..base import BaseAgent, AgentContext, AgentResult, AgentPhase
from .schema import ProseInput, ReasoningOutput


class ProseReasonerAgent(BaseAgent[ProseInput, ReasoningOutput]):
    """
    Pre-prose reasoning to plan the writing approach.

    Thinks through voice, pacing, and technical considerations
    before prose generation begins.
    """

    phase = AgentPhase.PROSE_GENERATION
    name = "Prose Reasoner"
    description = "Plan prose approach before writing"
    requires_approval = False

    async def execute(
        self,
        input_data: ProseInput,
        context: AgentContext
    ) -> AgentResult[ReasoningOutput]:
        """Execute prose reasoning."""
        start_time = time.time()

        try:
            author_name = context.author_profile.get("name", "Unknown Author")

            system_prompt, user_prompt = self.prompts.render(
                "prose_reasoning",
                author_name=author_name,
                author_style_guide=input_data.author_style_guide,
                chapter_blueprint=input_data.chapter_blueprint,
                story_bible=input_data.story_bible
            )

            response = await self.llm.generate(
                prompt=user_prompt,
                system=system_prompt,
                max_tokens=1500
            )

            context.add_token_usage(response.input_tokens, response.output_tokens)

            output = self._parse_reasoning(response.text)

            execution_time_ms = int((time.time() - start_time) * 1000)

            return AgentResult.success_result(
                output=output,
                reasoning="Planned prose approach",
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                execution_time_ms=execution_time_ms
            )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            return AgentResult.failure_result(
                error=f"Prose reasoning failed: {str(e)}",
                execution_time_ms=execution_time_ms
            )

    def _parse_reasoning(self, raw_text: str) -> ReasoningOutput:
        """Parse reasoning text. This doesn't need structured extraction."""
        sections = {
            "voice_calibration": "",
            "opening_strategy": "",
            "scene_transitions": "",
            "dialogue_approach": "",
            "pacing_implementation": "",
            "potential_challenges": "",
            "key_moments": "",
            "consistency_checks": ""
        }

        current_section = None
        current_content = []

        for line in raw_text.split('\n'):
            line_lower = line.lower().strip()

            # Detect section headers
            if 'voice' in line_lower and ('calibration' in line_lower or ':' in line):
                if current_section:
                    sections[current_section] = '\n'.join(current_content).strip()
                current_section = "voice_calibration"
                current_content = []
            elif 'opening' in line_lower and ('strategy' in line_lower or ':' in line):
                if current_section:
                    sections[current_section] = '\n'.join(current_content).strip()
                current_section = "opening_strategy"
                current_content = []
            elif 'transition' in line_lower:
                if current_section:
                    sections[current_section] = '\n'.join(current_content).strip()
                current_section = "scene_transitions"
                current_content = []
            elif 'dialogue' in line_lower:
                if current_section:
                    sections[current_section] = '\n'.join(current_content).strip()
                current_section = "dialogue_approach"
                current_content = []
            elif 'pacing' in line_lower:
                if current_section:
                    sections[current_section] = '\n'.join(current_content).strip()
                current_section = "pacing_implementation"
                current_content = []
            elif 'challenge' in line_lower:
                if current_section:
                    sections[current_section] = '\n'.join(current_content).strip()
                current_section = "potential_challenges"
                current_content = []
            elif 'key moment' in line_lower:
                if current_section:
                    sections[current_section] = '\n'.join(current_content).strip()
                current_section = "key_moments"
                current_content = []
            elif 'consistency' in line_lower:
                if current_section:
                    sections[current_section] = '\n'.join(current_content).strip()
                current_section = "consistency_checks"
                current_content = []
            elif current_section:
                current_content.append(line)

        if current_section:
            sections[current_section] = '\n'.join(current_content).strip()

        # If parsing didn't work well, put everything in voice_calibration
        if not any(sections.values()):
            sections["voice_calibration"] = raw_text

        return ReasoningOutput(**sections)
