"""Cost tracking database model."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func

from ..database import Base


class CostRecord(Base):
    """Tracks API costs per project."""

    __tablename__ = "cost_records"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    phase = Column(String(100), nullable=True)
    model = Column(String(100), nullable=True)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    cost_cents = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
