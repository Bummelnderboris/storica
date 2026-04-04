"""Author-related schemas."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class AuthorSummary(BaseModel):
    """Schema for author list item."""

    id: str
    name: str
    lived: str
    nationality: str


class AuthorDetail(BaseModel):
    """Full author profile with flexible structure."""

    id: str
    name: str
    lived: str
    nationality: str
    philosophy: Dict[str, Any] = {}
    structure: Dict[str, Any] = {}
    characters: Dict[str, Any] = {}
    prose: Dict[str, Any] = {}
    themes: List[str] = []
    examples: List[str] = []
    influences: List[str] = []
