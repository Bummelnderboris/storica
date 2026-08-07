"""Prose Critic Agent - evaluates generated prose."""

import json
import time
from typing import Any

from ..base import BaseAgent, AgentContext, AgentResult, AgentPhase
from .schema import ProseOutput, CritiqueOutput, CritiqueScore, CritiqueIssue


class CritiqueInput:
    """Input for critique."""
    def __init__(
        self,
        prose: str,
        chapter_blueprint: str,
        author_style_guide: str,
        critique_rubric: dict,
        story_bible: str
    ):
        self.prose = prose
        self.chapter_blueprint = chapter_blueprint
        self.author_style_guide = author_style_guide
        self.critique_rubric = critique_rubric
        self.story_bible = story_bible


class ProseCriticAgent(BaseAgent):
    """
    Critiques generated prose against author style and story requirements.

    Evaluates voice authenticity, blueprint adherence, consistency,
    and prose quality.
    """

    phase = AgentPhase.PROSE_GENERATION
    name = "Prose Critic"
    description = "Critique prose against author style and requirements"
    requires_approval = False

    PASSING_THRESHOLD = 7.0

    async def execute(
        self,
        input_data: CritiqueInput,
        context: AgentContext
    ) -> AgentResult[CritiqueOutput]:
        """Execute prose critique."""
        start_time = time.time()

        try:
            author_name = context.author_profile.get("name", "Unknown Author")

            # Format critique rubric
            rubric_text = json.dumps(input_data.critique_rubric, indent=2)

            system_prompt, user_prompt = self.prompts.render(
                "prose_critique",
                author_name=author_name,
                author_style_guide=input_data.author_style_guide,
                critique_rubric=rubric_text,
                chapter_blueprint=input_data.chapter_blueprint,
                prose=input_data.prose,
                story_bible=input_data.story_bible
            )

            response = await self.llm.generate(
                prompt=user_prompt,
                system=system_prompt,
                max_tokens=2000
            )

            context.add_token_usage(response.input_tokens, response.output_tokens)

            output = await self._parse_critique(response.text, context)

            execution_time_ms = int((time.time() - start_time) * 1000)

            return AgentResult.success_result(
                output=output,
                reasoning=f"Critique score: {output.overall_score:.1f}/10",
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                execution_time_ms=execution_time_ms
            )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            return AgentResult.failure_result(
                error=f"Critique failed: {str(e)}",
                execution_time_ms=execution_time_ms
            )

    async def _parse_critique(
        self,
        raw_text: str,
        context: AgentContext
    ) -> CritiqueOutput:
        """Parse critique into structured output."""

        extraction_prompt = f"""
Extract critique from this text into JSON:

{raw_text}

Return ONLY valid JSON:
{{
    "scores": [
        {{"category": "Voice Authenticity", "score": 8.0, "feedback": "..."}},
        {{"category": "Blueprint Adherence", "score": 7.5, "feedback": "..."}},
        {{"category": "Story Consistency", "score": 8.0, "feedback": "..."}},
        {{"category": "Prose Quality", "score": 7.0, "feedback": "..."}}
    ],
    "issues": [
        {{"description": "...", "severity": "major", "location": "paragraph 3", "suggestion": "..."}}
    ],
    "revision_priorities": ["priority1", "priority2"]
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

            scores = [CritiqueScore(**s) for s in data.get("scores", [])]
            issues = [CritiqueIssue(**i) for i in data.get("issues", [])]

            overall_score = sum(s.score for s in scores) / len(scores) if scores else 5.0

            return CritiqueOutput(
                scores=scores,
                overall_score=overall_score,
                issues=issues,
                revision_priorities=data.get("revision_priorities", []),
                passes_threshold=overall_score >= self.PASSING_THRESHOLD
            )
        except (json.JSONDecodeError, KeyError) as e:
            # Fallback with neutral scores
            return CritiqueOutput(
                scores=[
                    CritiqueScore(category="Overall", score=6.0, feedback=raw_text[:500])
                ],
                overall_score=6.0,
                issues=[],
                revision_priorities=["Review manually"],
                passes_threshold=False
            )
