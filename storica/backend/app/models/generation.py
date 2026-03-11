"""Generation task model for tracking async generation."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.project import Project


class TaskType(str, enum.Enum):
    """Types of generation tasks."""

    ESSENCE = "essence"
    ARCHITECTURE = "architecture"
    BLUEPRINT = "blueprint"
    CHAPTER = "chapter"
    POLISH = "polish"


class TaskStatus(str, enum.Enum):
    """Status of generation tasks."""

    PENDING = "pending"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REGENERATING = "regenerating"
    COMPLETED = "completed"
    FAILED = "failed"


class GenerationTask(Base):
    """Model for tracking generation tasks."""

    __tablename__ = "generation_tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    task_type: Mapped[TaskType] = mapped_column(Enum(TaskType))
    chapter_num: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.PENDING
    )
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    guidance: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    progress_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    project: Mapped["Project"] = relationship(
        "Project", back_populates="generation_tasks"
    )
