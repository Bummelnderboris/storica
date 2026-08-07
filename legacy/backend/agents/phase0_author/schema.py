"""Schemas for Author Mind Loading phase."""

from pydantic import BaseModel, Field
from typing import Optional


class AuthorMindInput(BaseModel):
    """Input for author mind loading."""
    author_id: str = Field(..., description="Author profile ID to load")


class AuthorMindOutput(BaseModel):
    """Output from author mind loading."""
    author_id: str
    author_name: str
    primary_language: str
    philosophy_summary: str
    style_guide: str
    character_patterns: str
    critique_rubric: dict
    loaded: bool = True
