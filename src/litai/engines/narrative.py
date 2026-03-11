"""Narrative generation engine for stages 1-3."""

from typing import Optional

from .author import AuthorProfile
from ..llm.client import LLMClient
from ..llm.prompts import PromptTemplates


class NarrativeEngine:
    """Generates narrative structure documents."""

    def __init__(self, llm_client: LLMClient, author_engine):
        self.llm_client = llm_client
        self.author_engine = author_engine

    def generate_essence(
        self,
        seed: str,
        author_profile: AuthorProfile,
        guidance: Optional[str] = None,
    ) -> str:
        """Generate the essence document (Stage 1)."""
        prompt = PromptTemplates.essence(
            seed=seed,
            author_profile=author_profile,
            guidance=guidance,
        )

        return self.llm_client.generate(prompt)

    def generate_architecture(
        self,
        essence: str,
        author_profile: AuthorProfile,
        target_words: int,
        guidance: Optional[str] = None,
    ) -> str:
        """Generate the narrative architecture (Stage 2)."""
        prompt = PromptTemplates.architecture(
            essence=essence,
            author_profile=author_profile,
            target_words=target_words,
            guidance=guidance,
        )

        return self.llm_client.generate(prompt)

    def generate_blueprint(
        self,
        chapter_num: int,
        architecture: str,
        author_profile: AuthorProfile,
        previous_blueprints: dict[int, str],
        guidance: Optional[str] = None,
    ) -> str:
        """Generate a chapter blueprint (Stage 3)."""
        prompt = PromptTemplates.blueprint(
            chapter_num=chapter_num,
            architecture=architecture,
            author_profile=author_profile,
            previous_blueprints=previous_blueprints,
            guidance=guidance,
        )

        return self.llm_client.generate(prompt)
