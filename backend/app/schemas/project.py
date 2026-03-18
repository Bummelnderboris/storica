"""Project-related schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.project import ProjectStage


class ProjectCreate(BaseModel):
    """Schema for creating a project."""

    name: str
    author_id: str
    target_words: int = 45000
    seed: Optional[str] = None


class ProjectUpdate(BaseModel):
    """Schema for updating a project."""

    name: Optional[str] = None
    seed: Optional[str] = None
    target_words: Optional[int] = None


class ProjectResponse(BaseModel):
    """Schema for project in list response."""

    id: int
    name: str
    author_id: str
    target_words: int
    current_stage: ProjectStage
    current_chapter: int
    total_chapters: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    """Schema for project list response."""

    projects: list[ProjectResponse]
    total: int


class ContentSummary(BaseModel):
    """Summary of project content."""

    has_essence: bool = False
    has_architecture: bool = False
    has_story_bible: bool = False
    blueprint_count: int = 0
    chapter_count: int = 0
    total_word_count: int = 0


class ProjectDetailResponse(BaseModel):
    """Schema for detailed project response."""

    id: int
    name: str
    author_id: str
    target_words: int
    current_stage: ProjectStage
    current_chapter: int
    total_chapters: int
    seed: Optional[str]
    content_summary: ContentSummary
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
