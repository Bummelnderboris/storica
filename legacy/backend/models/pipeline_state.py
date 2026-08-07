"""Pipeline state database models."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship

from ..database import Base


class PipelineRun(Base):
    """Tracks pipeline executions."""

    __tablename__ = "pipeline_runs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(50), nullable=False, default="not_started")
    current_phase = Column(String(100), nullable=True)
    author_id = Column(String(100), nullable=True)
    author_language = Column(String(10), nullable=True)
    current_chapter = Column(Integer, default=0)
    total_chapters = Column(Integer, default=0)
    total_input_tokens = Column(Integer, default=0)
    total_output_tokens = Column(Integer, default=0)
    state_json = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    paused_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # Relationships
    project = relationship("Project", back_populates="pipeline_runs")
    phase_results = relationship("PhaseResult", back_populates="pipeline_run", cascade="all, delete-orphan")


class PhaseResult(Base):
    """Stores results of each pipeline phase."""

    __tablename__ = "phase_results"

    id = Column(Integer, primary_key=True, index=True)
    pipeline_run_id = Column(Integer, ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False)
    phase_name = Column(String(100), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="pending")
    output_json = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    execution_time_ms = Column(Integer, default=0)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    pipeline_run = relationship("PipelineRun", back_populates="phase_results")
