"""Consistency Guardian Agent - checks and maintains story consistency."""

import json
import time
from typing import Any

from ..base import BaseAgent, AgentContext, AgentResult, AgentPhase
from ..registry import AgentRegistry
from .schema import (
    ConsistencyInput,
    ConsistencyOutput,
    ConsistencyIssue,
    StoryBibleUpdate
)
from .story_bible import StoryBible


@AgentRegistry.register(AgentPhase.CONSISTENCY_CHECK)
class ConsistencyGuardianAgent(BaseAgent[ConsistencyInput, ConsistencyOutput]):
    """
    Phase 7: Check chapter consistency and update story bible.

    Ensures narrative consistency by checking new content against
    the story bible and extracting new facts to add.
    """

    phase = AgentPhase.CONSISTENCY_CHECK
    name = "Consistency Guardian"
    description = "Check consistency and update story bible"
    requires_approval = False

    async def execute(
        self,
        input_data: ConsistencyInput,
        context: AgentContext
    ) -> AgentResult[ConsistencyOutput]:
        """Execute consistency check."""
        start_time = time.time()

        try:
            # Load story bible
            story_bible = StoryBible.from_json(input_data.story_bible_json)
            bible_summary = story_bible.to_prompt_summary()

            system_prompt, user_prompt = self.prompts.render(
                "consistency_check",
                chapter_index=input_data.chapter_index,
                chapter_prose=input_data.chapter_prose,
                story_bible=bible_summary
            )

            response = await self.llm.generate(
                prompt=user_prompt,
                system=system_prompt,
                max_tokens=2500
            )

            context.add_token_usage(response.input_tokens, response.output_tokens)

            output = await self._parse_check(
                response.text, input_data.chapter_index, context
            )

            # Apply updates to story bible
            story_bible.apply_updates(output.updates)
            context.story_bible = json.loads(story_bible.to_json())

            execution_time_ms = int((time.time() - start_time) * 1000)

            return AgentResult.success_result(
                output=output,
                reasoning=f"Found {len(output.issues_found)} issues, {len(output.updates)} updates",
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                execution_time_ms=execution_time_ms
            )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            return AgentResult.failure_result(
                error=f"Consistency check failed: {str(e)}",
                execution_time_ms=execution_time_ms
            )

    async def _parse_check(
        self,
        raw_text: str,
        chapter_index: int,
        context: AgentContext
    ) -> ConsistencyOutput:
        """Parse consistency check into structured output."""

        extraction_prompt = f"""
Extract consistency check results from this text into JSON:

{raw_text}

Return ONLY valid JSON:
{{
    "issues_found": [
        {{
            "category": "character",
            "description": "Issue description",
            "established": "What was previously established",
            "new_content": "What the new chapter says",
            "severity": "critical",
            "suggestion": "How to fix"
        }}
    ],
    "updates": [
        {{
            "category": "character",
            "key": "Character Name",
            "value": "New info about character",
            "chapter_introduced": {chapter_index}
        }}
    ],
    "summary": "Brief summary of findings"
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

            issues = [
                ConsistencyIssue(**issue)
                for issue in data.get("issues_found", [])
            ]

            updates = [
                StoryBibleUpdate(**update)
                for update in data.get("updates", [])
            ]

            has_critical = any(i.severity == "critical" for i in issues)

            return ConsistencyOutput(
                chapter_index=chapter_index,
                issues_found=issues,
                has_critical_issues=has_critical,
                updates=updates,
                summary=data.get("summary", "")
            )

        except (json.JSONDecodeError, KeyError) as e:
            # Return empty result on parse failure
            return ConsistencyOutput(
                chapter_index=chapter_index,
                issues_found=[],
                has_critical_issues=False,
                updates=[],
                summary=f"Parse error: {e}"
            )
