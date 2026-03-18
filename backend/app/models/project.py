"""Project and content models."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.generation import GenerationTask
    from app.models.cost import CostRecord


class ProjectStage(str, enum.Enum):
    """Project workflow stages."""

    ESSENCE = "essence"
    ARCHITECTURE = "architecture"
    BLUEPRINT = "blueprint"
    PROSE = "prose"
    POLISH = "polish"
    COMPLETE = "complete"


class ContentType(str, enum.Enum):
    """Types of project content."""

    ESSENCE = "essence"
    ARCHITECTURE = "architecture"
    STORY_BIBLE = "story_bible"


class Project(Base):
    """Project model representing a novel generation project."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    author_id: Mapped[str] = mapped_column(String(100))
    target_words: Mapped[int] = mapped_column(Integer, default=45000)
    current_stage: Mapped[ProjectStage] = mapped_column(
        Enum(ProjectStage), default=ProjectStage.ESSENCE
    )
    current_chapter: Mapped[int] = mapped_column(Integer, default=0)
    total_chapters: Mapped[int] = mapped_column(Integer, default=0)
    seed: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="projects")
    contents: Mapped[list["ProjectContent"]] = relationship(
        "ProjectContent", back_populates="project", cascade="all, delete-orphan"
    )
    blueprints: Mapped[list["Blueprint"]] = relationship(
        "Blueprint", back_populates="project", cascade="all, delete-orphan"
    )
    chapters: Mapped[list["Chapter"]] = relationship(
        "Chapter", back_populates="project", cascade="all, delete-orphan"
    )
    generation_tasks: Mapped[list["GenerationTask"]] = relationship(
        "GenerationTask", back_populates="project", cascade="all, delete-orphan"
    )
    cost_records: Mapped[list["CostRecord"]] = relationship(
        "CostRecord", back_populates="project", cascade="all, delete-orphan"
    )


class ProjectContent(Base):
    """Versioned content for project (essence, architecture, story_bible)."""

    __tablename__ = "project_content"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    content_type: Mapped[ContentType] = mapped_column(Enum(ContentType))
    content: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="contents")


class Blueprint(Base):
    """Chapter blueprint model."""

    __tablename__ = "blueprints"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    chapter_num: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="blueprints")


class Chapter(Base):
    """Generated chapter model."""

    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    chapter_num: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="chapters")
