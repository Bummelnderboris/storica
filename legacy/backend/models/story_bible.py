"""Story Bible database model."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship

from ..database import Base


class StoryBible(Base):
    """Persistent story bible storage."""

    __tablename__ = "story_bibles"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    bible_json = Column(Text, nullable=False, default="{}")
    version = Column(Integer, default=1)
    last_chapter_updated = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # Relationships
    project = relationship("Project", back_populates="story_bible")
