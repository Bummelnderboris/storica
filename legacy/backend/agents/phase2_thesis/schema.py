"""Schemas for Thesis Development phase."""

from pydantic import BaseModel, Field
from typing import List


class ThesisDevelopmentInput(BaseModel):
    """Input for thesis development."""
    topic_exploration: str = Field(..., description="Output from topic exploration")
    story_dna_summary: str = Field(..., description="Story DNA summary")


class ThesisDevelopmentOutput(BaseModel):
    """Output from thesis development."""
    central_thesis: str = Field(
        ...,
        description="One sentence thesis about the human condition"
    )
    antithesis: str = Field(
        ...,
        description="The opposing view that will be challenged"
    )
    thematic_questions: List[str] = Field(
        ...,
        description="Questions the story will explore",
        min_length=3
    )
    moral_complexity: str = Field(
        ...,
        description="How the story avoids simple moralizing"
    )
    author_resonance: str = Field(
        ...,
        description="How this connects to the author's body of work"
    )
