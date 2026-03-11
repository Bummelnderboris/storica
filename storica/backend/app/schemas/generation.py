"""Generation task schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.generation import TaskType, TaskStatus


class GenerationTaskCreate(BaseModel):
    """Schema for starting a generation task."""

    guidance: Optional[str] = None


class GenerationTaskResponse(BaseModel):
    """Schema for generation task response."""

    id: int
    project_id: int
    task_type: TaskType
    chapter_num: Optional[int]
    status: TaskStatus
    progress_percent: int
    progress_message: Optional[str]
    result_preview: Optional[str] = None
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GenerationApproval(BaseModel):
    """Schema for approving generated content."""

    approved: bool = True


class GenerationRegenerate(BaseModel):
    """Schema for regenerating content with guidance."""

    guidance: str
