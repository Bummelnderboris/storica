"""Project and Chapter database models."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, func
from sqlalchemy.orm import relationship

from ..database import Base


class Project(Base):
    """A novel project."""

    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    author_id = Column(String(100), nullable=True)
    status = Column(String(50), default="draft")

    # Story DNA and pipeline outputs (JSON columns)
    story_dna_json = Column(Text, nullable=True)
    topic_analysis_json = Column(Text, nullable=True)
    story_thesis_json = Column(Text, nullable=True)
    character_system_json = Column(Text, nullable=True)
    story_architecture_json = Column(Text, nullable=True)

    # Statistics
    total_words = Column(Integer, default=0)
    chapter_count = Column(Integer, default=0)

    # Cost tracking
    total_input_tokens = Column(Integer, default=0)
    total_output_tokens = Column(Integer, default=0)
    estimated_cost = Column(Integer, default=0)  # In cents

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="projects")
    chapters = relationship("Chapter", back_populates="project", cascade="all, delete-orphan", order_by="Chapter.chapter_number")
    pipeline_runs = relationship("PipelineRun", back_populates="project", cascade="all, delete-orphan")
    story_bible = relationship("StoryBible", back_populates="project", uselist=False, cascade="all, delete-orphan")


class Chapter(Base):
    """A chapter within a project."""

    __tablename__ = "chapters"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    chapter_number = Column(Integer, nullable=False)
    title = Column(String(255), nullable=True)
    content = Column(Text, nullable=True)
    blueprint_json = Column(Text, nullable=True)

    # Status
    status = Column(String(50), default="pending")
    is_approved = Column(Boolean, default=False)

    # Statistics
    word_count = Column(Integer, default=0)

    # Critique data
    final_score = Column(Integer, nullable=True)  # Score * 10 for precision
    critique_iterations = Column(Integer, default=0)

    # Cost tracking
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # Relationships
    project = relationship("Project", back_populates="chapters")
