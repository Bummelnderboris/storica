"""Schemas for Prose Generation phase."""

from pydantic import BaseModel, Field
from typing import List, Optional


class ProseInput(BaseModel):
    """Input for prose generation."""
    chapter_blueprint: str
    story_bible: str
    author_style_guide: str
    author_language: str


class ReasoningOutput(BaseModel):
    """Output from prose reasoning."""
    voice_calibration: str
    opening_strategy: str
    scene_transitions: str
    dialogue_approach: str
    pacing_implementation: str
    potential_challenges: str
    key_moments: str
    consistency_checks: str


class ProseOutput(BaseModel):
    """Output from prose writing."""
    prose: str
    word_count: int


class CritiqueScore(BaseModel):
    """Individual critique score."""
    category: str
    score: float = Field(..., ge=1, le=10)
    feedback: str


class CritiqueIssue(BaseModel):
    """A specific issue found."""
    description: str
    severity: str  # critical, major, minor
    location: Optional[str] = None
    suggestion: str


class CritiqueOutput(BaseModel):
    """Output from prose critique."""
    scores: List[CritiqueScore]
    overall_score: float = Field(..., ge=1, le=10)
    issues: List[CritiqueIssue]
    revision_priorities: List[str]
    passes_threshold: bool


class RevisionOutput(BaseModel):
    """Output from prose revision."""
    revised_prose: str
    word_count: int
    changes_made: List[str]


class ProseLoopResult(BaseModel):
    """Final result from prose generation loop."""
    final_prose: str
    word_count: int
    iterations: int
    final_score: float
    critique_history: List[CritiqueOutput]
