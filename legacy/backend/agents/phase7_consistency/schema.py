"""Schemas for Consistency Guardian phase."""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime


class ConsistencyInput(BaseModel):
    """Input for consistency check."""
    chapter_index: int
    chapter_prose: str
    story_bible_json: str


class ConsistencyIssue(BaseModel):
    """A consistency issue found."""
    category: str  # character, setting, plot, object
    description: str
    established: str
    new_content: str
    severity: str  # critical, minor
    suggestion: str


class StoryBibleUpdate(BaseModel):
    """An update to add to the story bible."""
    category: str
    key: str
    value: str
    chapter_introduced: int


class ConsistencyOutput(BaseModel):
    """Output from consistency check."""
    chapter_index: int
    issues_found: List[ConsistencyIssue]
    has_critical_issues: bool
    updates: List[StoryBibleUpdate]
    summary: str


# Story Bible Types

class StoryBibleCharacter(BaseModel):
    """A character in the story bible."""
    name: str
    description: str
    first_appearance: int
    last_seen: int
    key_traits: List[str] = []
    relationships: Dict[str, str] = {}
    status: str = "alive"


class StoryBibleLocation(BaseModel):
    """A location in the story bible."""
    name: str
    description: str
    first_mentioned: int
    details: Dict[str, str] = {}


class StoryBibleEvent(BaseModel):
    """A timeline event."""
    chapter: int
    description: str
    characters_involved: List[str] = []
    significance: str = ""


class StoryBibleObject(BaseModel):
    """A significant object."""
    name: str
    description: str
    first_mentioned: int
    current_location: Optional[str] = None
    significance: str = ""


class StoryBibleData(BaseModel):
    """Complete story bible data."""
    characters: Dict[str, StoryBibleCharacter] = {}
    locations: Dict[str, StoryBibleLocation] = {}
    timeline: List[StoryBibleEvent] = []
    objects: Dict[str, StoryBibleObject] = {}
    foreshadowing: List[str] = []
    established_facts: Dict[str, str] = {}
    last_updated: Optional[datetime] = None
