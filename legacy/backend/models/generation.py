"""Generation task database model."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship

from ..database import Base


class GenerationTask(Base):
    """Tracks generation task executions (legacy, kept for compatibility)."""

    __tablename__ = "generation_tasks"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    task_type = Column(String(100), nullable=False)
    status = Column(String(50), default="pending")
    celery_task_id = Column(String(255), nullable=True)
    input_json = Column(Text, nullable=True)
    output_json = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
