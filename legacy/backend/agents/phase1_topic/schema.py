"""Schemas for Topic Exploration phase."""

from pydantic import BaseModel, Field
from typing import List, Optional


class TopicExplorationInput(BaseModel):
    """Input for topic exploration."""
    story_spark: str = Field(..., description="The initial story spark/idea")
    genre: str = Field(..., description="Primary genre")
    subgenres: List[str] = Field(default_factory=list)


class ThematicDepth(BaseModel):
    """Explored thematic depth."""
    theme: str
    interpretation: str
    author_angle: str


class PhilosophicalAngle(BaseModel):
    """Philosophical question to explore."""
    question: str
    exploration_direction: str


class TopicExplorationOutput(BaseModel):
    """Output from topic exploration."""
    thematic_depths: List[ThematicDepth] = Field(
        ...,
        description="Deep thematic interpretations",
        min_length=2
    )
    philosophical_angles: List[PhilosophicalAngle] = Field(
        ...,
        description="Philosophical questions to explore",
        min_length=2
    )
    ironic_possibilities: List[str] = Field(
        ...,
        description="Paradoxes and ironies to exploit"
    )
    central_tension: str = Field(
        ...,
        description="The core conflict or question"
    )
    unique_angle: str = Field(
        ...,
        description="What makes this story distinctive"
    )
    raw_exploration: str = Field(
        ...,
        description="Full exploration text"
    )
