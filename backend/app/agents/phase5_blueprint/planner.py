"""Blueprint Planner Agent - creates detailed chapter blueprints."""

import json
import time
from typing import Any

from ..base import BaseAgent, AgentContext, AgentResult, AgentPhase
from ..registry import AgentRegistry
from .schema import (
    BlueprintInput,
    BlueprintOutput,
    Scene,
    SceneBeat,
    EmotionalArc
)


@AgentRegistry.register(AgentPhase.CHAPTER_BLUEPRINTS)
class BlueprintPlannerAgent(BaseAgent[BlueprintInput, BlueprintOutput]):
    """
    Phase 5: Create detailed chapter blueprints.

    Generates a precise plan for each chapter that guides prose generation.
    """

    phase = AgentPhase.CHAPTER_BLUEPRINTS
    name = "Blueprint Planner"
    description = "Create detailed chapter blueprints for prose generation"
    requires_approval = False  # Auto-approved, prose requires approval instead

    async def execute(
        self,
        input_data: BlueprintInput,
        context: AgentContext
    ) -> AgentResult[BlueprintOutput]:
        """Execute blueprint generation."""
        start_time = time.time()

        try:
            author_name = context.author_profile.get("name", "Unknown Author")

            system_prompt, user_prompt = self.prompts.render(
                "chapter_blueprint",
                author_name=author_name,
                chapter_index=input_data.chapter_index,
                chapter_purpose=input_data.chapter_purpose,
                story_architecture=input_data.story_architecture,
                characters=input_data.characters,
                previous_chapter_summary=input_data.previous_chapter_summary or "This is the first chapter.",
                story_bible=input_data.story_bible
            )

            response = await self.llm.generate(
                prompt=user_prompt,
                system=system_prompt,
                max_tokens=3500
            )

            context.add_token_usage(response.input_tokens, response.output_tokens)

            output = await self._parse_blueprint(
                response.text, input_data.chapter_index, context
            )

            execution_time_ms = int((time.time() - start_time) * 1000)

            return AgentResult.success_result(
                output=output,
                reasoning=f"Created blueprint for chapter {input_data.chapter_index} with {len(output.scenes)} scenes",
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                execution_time_ms=execution_time_ms,
                requires_approval=False
            )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            return AgentResult.failure_result(
                error=f"Blueprint generation failed: {str(e)}",
                execution_time_ms=execution_time_ms
            )

    async def _parse_blueprint(
        self,
        raw_text: str,
        chapter_index: int,
        context: AgentContext
    ) -> BlueprintOutput:
        """Parse blueprint into structured output."""

        extraction_prompt = f"""
Extract chapter blueprint from this text into JSON:

{raw_text}

Return ONLY valid JSON:
{{
    "opening_hook": "First line/image",
    "establishing_details": "What reader needs immediately",
    "pov_tense": "e.g. Third limited, past tense",
    "scenes": [
        {{
            "scene_number": 1,
            "location": "...",
            "characters_present": ["name1", "name2"],
            "scene_goal": "...",
            "conflict_tension": "...",
            "beats": [{{"number": 1, "description": "..."}}, {{"number": 2, "description": "..."}}],
            "dialogue_notes": ["key line 1"],
            "subtext": "...",
            "sensory_details": ["detail1"],
            "transition": "..."
        }}
    ],
    "emotional_arc": {{
        "start": "...",
        "shift": "...",
        "end": "..."
    }},
    "final_image": "...",
    "hook_forward": "...",
    "word_count_target": 3500,
    "pacing_notes": "...",
    "style_notes": "..."
}}
"""

        response = await self.llm.generate(
            prompt=extraction_prompt,
            system="Extract structured data. Return only valid JSON.",
            max_tokens=2500
        )

        context.add_token_usage(response.input_tokens, response.output_tokens)

        try:
            text = response.text.strip()
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]

            data = json.loads(text.strip())

            scenes = []
            for scene_data in data.get("scenes", []):
                beats = [
                    SceneBeat(**beat) for beat in scene_data.get("beats", [])
                ]
                scene = Scene(
                    scene_number=scene_data.get("scene_number", 1),
                    location=scene_data.get("location", ""),
                    characters_present=scene_data.get("characters_present", []),
                    scene_goal=scene_data.get("scene_goal", ""),
                    conflict_tension=scene_data.get("conflict_tension", ""),
                    beats=beats,
                    dialogue_notes=scene_data.get("dialogue_notes", []),
                    subtext=scene_data.get("subtext", ""),
                    sensory_details=scene_data.get("sensory_details", []),
                    transition=scene_data.get("transition", "")
                )
                scenes.append(scene)

            emotional_arc_data = data.get("emotional_arc", {})

            return BlueprintOutput(
                chapter_index=chapter_index,
                opening_hook=data.get("opening_hook", ""),
                establishing_details=data.get("establishing_details", ""),
                pov_tense=data.get("pov_tense", "Third limited, past tense"),
                scenes=scenes,
                emotional_arc=EmotionalArc(
                    start=emotional_arc_data.get("start", ""),
                    shift=emotional_arc_data.get("shift", ""),
                    end=emotional_arc_data.get("end", "")
                ),
                final_image=data.get("final_image", ""),
                hook_forward=data.get("hook_forward", ""),
                word_count_target=data.get("word_count_target", 3500),
                pacing_notes=data.get("pacing_notes", ""),
                style_notes=data.get("style_notes", ""),
                raw_blueprint=raw_text
            )
        except (json.JSONDecodeError, KeyError) as e:
            raise ValueError(f"Failed to parse blueprint: {e}")
