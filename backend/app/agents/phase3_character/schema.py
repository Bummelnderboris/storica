"""Schemas for Character Derivation phase."""

from pydantic import BaseModel, Field
from typing import List, Optional


class CharacterDerivationInput(BaseModel):
    """Input for character derivation."""
    story_thesis: str
    story_dna_characters: str
    author_character_patterns: str


class Protagonist(BaseModel):
    """Protagonist details."""
    name: str
    core_want: str
    core_need: str
    fatal_flaw: str
    contradictions: str
    voice: str
    arc: str


class Antagonist(BaseModel):
    """Antagonist details."""
    nature: str
    motivation: str
    relationship_to_thesis: str
    complexity: str
    name: Optional[str] = None


class SupportingCharacter(BaseModel):
    """Supporting character details."""
    name: str
    role: str
    relationship: str
    thematic_purpose: str
    distinctive_trait: str


class CharacterDerivationOutput(BaseModel):
    """Output from character derivation."""
    protagonist: Protagonist
    antagonist: Antagonist
    supporting_cast: List[SupportingCharacter] = Field(default_factory=list)
    character_dynamics: str = Field(
        ...,
        description="How characters create friction with each other"
    )
