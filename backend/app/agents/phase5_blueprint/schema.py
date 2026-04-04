"""Schemas for Chapter Blueprint phase."""

from pydantic import BaseModel, Field
from typing import List, Optional


class BlueprintInput(BaseModel):
    """Input for chapter blueprint generation."""
    chapter_index: int
    chapter_purpose: str
    story_architecture: str
    characters: str
    previous_chapter_summary: Optional[str] = None
    story_bible: str


class SceneBeat(BaseModel):
    """A beat within a scene."""
    number: int
    description: str


class Scene(BaseModel):
    """A scene within a chapter."""
    scene_number: int
    location: str
    characters_present: List[str]
    scene_goal: str
    conflict_tension: str
    beats: List[SceneBeat]
    dialogue_notes: List[str]
    subtext: str
    sensory_details: List[str]
    transition: str


class EmotionalArc(BaseModel):
    """Emotional arc of the chapter."""
    start: str
    shift: str
    end: str


class BlueprintOutput(BaseModel):
    """Output from blueprint generation."""
    chapter_index: int
    opening_hook: str
    establishing_details: str
    pov_tense: str
    scenes: List[Scene]
    emotional_arc: EmotionalArc
    final_image: str
    hook_forward: str
    word_count_target: int
    pacing_notes: str
    style_notes: str
    raw_blueprint: str
