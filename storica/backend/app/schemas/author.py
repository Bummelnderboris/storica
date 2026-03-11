"""Author-related schemas."""

from typing import Optional

from pydantic import BaseModel


class AuthorSummary(BaseModel):
    """Schema for author list item."""

    id: str
    name: str
    lived: str
    nationality: str


class AuthorPhilosophy(BaseModel):
    """Author's philosophical approach."""

    central_obsession: str
    worldview: str
    recurring_questions: list[str]
    modern_lens: dict[str, str]


class AuthorStructure(BaseModel):
    """Author's structural patterns."""

    signature_pattern: str
    description: str
    act_rhythm: list[str]
    endings: str
    favorite_devices: list[str]


class AuthorCharacters(BaseModel):
    """Author's character approach."""

    protagonists: str
    antagonists: str
    dialogue_style: str
    archetypes: list[str]


class AuthorProse(BaseModel):
    """Author's prose style."""

    sentence_rhythm: str
    vocabulary: str
    tone: str
    markers: list[str]
    avoid: list[str]


class AuthorExamples(BaseModel):
    """Example passages in author's style."""

    openings: list[str]
    dialogue: list[str]


class AuthorDetail(BaseModel):
    """Full author profile."""

    id: str
    name: str
    lived: str
    nationality: str
    philosophy: AuthorPhilosophy
    structure: AuthorStructure
    characters: AuthorCharacters
    prose: AuthorProse
    themes: dict[str, list[str]]
    examples: AuthorExamples
    influences: list[str]
