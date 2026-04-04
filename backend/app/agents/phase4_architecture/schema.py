"""Schemas for Story Architecture phase."""

from pydantic import BaseModel, Field
from typing import List, Dict


class StoryArchitectureInput(BaseModel):
    """Input for story architecture."""
    story_thesis: str
    characters: str
    structure_type: str
    chapter_count: int


class ActBreakdown(BaseModel):
    """Breakdown of a story act."""
    act_number: int
    purpose: str
    key_events: List[str]
    character_state: str
    tension_level: str
    chapters: List[int]


class TurningPoint(BaseModel):
    """Major story turning point."""
    name: str
    description: str
    chapter: int


class ChapterPacing(BaseModel):
    """Pacing info for a chapter."""
    chapter: int
    pacing: str  # fast/medium/slow
    tension: int  # 1-10
    focus: str


class StoryArchitectureOutput(BaseModel):
    """Output from story architecture."""
    acts: List[ActBreakdown]
    turning_points: List[TurningPoint]
    recurring_elements: List[str]
    parallel_structures: List[str]
    subplots: List[str]
    chapter_pacing: List[ChapterPacing]
    raw_architecture: str
