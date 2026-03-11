"""Prose generation engine for stage 4."""

from typing import Any, Optional

from .author import AuthorProfile
from ..llm.client import LLMClient
from ..llm.prompts import PromptTemplates


class ProseEngine:
    """Generates prose content."""

    def __init__(self, llm_client: LLMClient, author_engine):
        self.llm_client = llm_client
        self.author_engine = author_engine

    def generate_chapter(
        self,
        chapter_num: int,
        blueprint: str,
        author_profile: AuthorProfile,
        story_bible: dict[str, Any],
        previous_chapters: dict[int, str],
        guidance: Optional[str] = None,
    ) -> str:
        """Generate a chapter's prose (Stage 4)."""
        prompt = PromptTemplates.chapter(
            chapter_num=chapter_num,
            blueprint=blueprint,
            author_profile=author_profile,
            story_bible=story_bible,
            previous_chapters=previous_chapters,
            guidance=guidance,
        )

        return self.llm_client.generate(prompt, max_tokens=8000)

    def check_consistency(
        self,
        chapters: dict[int, str],
        story_bible: dict[str, Any],
        author_profile: AuthorProfile,
    ) -> Optional[str]:
        """Check for consistency issues across chapters."""
        prompt = PromptTemplates.consistency_check(
            chapters=chapters,
            story_bible=story_bible,
            author_profile=author_profile,
        )

        response = self.llm_client.generate(prompt)

        # If no issues found, return None
        if "no issues" in response.lower() or "no consistency" in response.lower():
            return None

        return response
