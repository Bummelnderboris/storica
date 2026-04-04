"""Prose Reviser Agent - revises prose based on critique."""

import time
from typing import Any

from ..base import BaseAgent, AgentContext, AgentResult, AgentPhase
from .schema import CritiqueOutput, RevisionOutput


class RevisionInput:
    """Input for revision."""
    def __init__(
        self,
        original_prose: str,
        critique: CritiqueOutput,
        author_style_guide: str,
        author_language: str
    ):
        self.original_prose = original_prose
        self.critique = critique
        self.author_style_guide = author_style_guide
        self.author_language = author_language


class ProseReviserAgent(BaseAgent):
    """
    Revises prose based on critique feedback.

    Addresses identified issues while maintaining author voice.
    """

    phase = AgentPhase.PROSE_GENERATION
    name = "Prose Reviser"
    description = "Revise prose based on critique feedback"
    requires_approval = True

    async def execute(
        self,
        input_data: RevisionInput,
        context: AgentContext
    ) -> AgentResult[RevisionOutput]:
        """Execute prose revision."""
        start_time = time.time()

        try:
            author_name = context.author_profile.get("name", "Unknown Author")

            # Format critique for prompt
            critique_text = self._format_critique(input_data.critique)
            priorities = "\n".join(
                f"- {p}" for p in input_data.critique.revision_priorities
            )

            system_prompt, user_prompt = self.prompts.render(
                "prose_revision",
                author_name=author_name,
                author_language=input_data.author_language,
                author_style_guide=input_data.author_style_guide,
                original_prose=input_data.original_prose,
                critique=critique_text,
                revision_priorities=priorities
            )

            response = await self.llm.generate(
                prompt=user_prompt,
                system=system_prompt,
                max_tokens=8000,
                model="opus"  # Higher quality for revisions
            )

            context.add_token_usage(response.input_tokens, response.output_tokens)

            revised_prose = response.text.strip()
            word_count = len(revised_prose.split())

            # Identify what changed
            changes = self._identify_changes(
                input_data.original_prose,
                revised_prose
            )

            output = RevisionOutput(
                revised_prose=revised_prose,
                word_count=word_count,
                changes_made=changes
            )

            execution_time_ms = int((time.time() - start_time) * 1000)

            return AgentResult.success_result(
                output=output,
                reasoning=f"Revised prose: {len(changes)} changes, {word_count} words",
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                execution_time_ms=execution_time_ms,
                requires_approval=True
            )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            return AgentResult.failure_result(
                error=f"Revision failed: {str(e)}",
                execution_time_ms=execution_time_ms
            )

    def _format_critique(self, critique: CritiqueOutput) -> str:
        """Format critique for the revision prompt."""
        parts = [f"Overall Score: {critique.overall_score:.1f}/10\n"]

        parts.append("Category Scores:")
        for score in critique.scores:
            parts.append(f"- {score.category}: {score.score}/10 - {score.feedback}")

        if critique.issues:
            parts.append("\nIssues Found:")
            for issue in critique.issues:
                location = f" ({issue.location})" if issue.location else ""
                parts.append(
                    f"- [{issue.severity}]{location}: {issue.description}"
                )
                parts.append(f"  Suggestion: {issue.suggestion}")

        return "\n".join(parts)

    def _identify_changes(self, original: str, revised: str) -> list[str]:
        """Identify what changed between original and revised prose."""
        changes = []

        orig_words = len(original.split())
        rev_words = len(revised.split())
        word_diff = rev_words - orig_words

        if word_diff > 50:
            changes.append(f"Added approximately {word_diff} words")
        elif word_diff < -50:
            changes.append(f"Removed approximately {abs(word_diff)} words")

        orig_paras = original.count('\n\n')
        rev_paras = revised.count('\n\n')
        if orig_paras != rev_paras:
            changes.append(f"Paragraph structure changed ({orig_paras} -> {rev_paras})")

        # Check for dialogue changes
        orig_quotes = original.count('"')
        rev_quotes = revised.count('"')
        if abs(orig_quotes - rev_quotes) > 4:
            changes.append("Dialogue sections modified")

        if not changes:
            changes.append("Minor edits and polish")

        return changes
