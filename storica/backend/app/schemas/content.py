"""Content-related schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.project import ContentType


class ContentResponse(BaseModel):
    """Schema for project content (essence, architecture, story_bible)."""

    id: int
    content_type: ContentType
    content: str
    version: int
    created_at: datetime

    model_config = {"from_attributes": True}


class BlueprintResponse(BaseModel):
    """Schema for blueprint response."""

    id: int
    chapter_num: int
    content: str
    version: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ChapterResponse(BaseModel):
    """Schema for chapter response."""

    id: int
    chapter_num: int
    content: str
    word_count: int
    version: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ChapterListResponse(BaseModel):
    """Schema for chapter list."""

    chapters: list[ChapterResponse]
    total_word_count: int


class BlueprintListResponse(BaseModel):
    """Schema for blueprint list."""

    blueprints: list[BlueprintResponse]
