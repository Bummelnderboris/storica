"""Pipeline-related Pydantic schemas."""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class PhaseOutput(BaseModel):
    """Generic phase output."""
    phase_name: str
    status: str
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    execution_time_ms: int = 0


class PipelineStatus(BaseModel):
    """Pipeline status response."""
    project_id: int
    status: str
    current_phase: Optional[str] = None
    current_chapter: int = 0
    total_chapters: int = 0
    progress_percent: float = 0.0
    phases: List[PhaseOutput] = []
    cost: Dict[str, Any] = {}
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ApprovalRequest(BaseModel):
    """Approval request for a phase."""
    gate_id: str
    phase_name: str
    project_id: int
    output_preview: Dict[str, Any]
    created_at: datetime


class CritiqueScore(BaseModel):
    """Critique score for prose."""
    category: str
    score: float = Field(..., ge=1, le=10)
    feedback: str


class CritiqueResult(BaseModel):
    """Critique result from prose evaluation."""
    iteration: int
    scores: List[CritiqueScore]
    overall_score: float
    passes_threshold: bool
    issues: List[str] = []
    revision_priorities: List[str] = []


class ChapterGenerationResult(BaseModel):
    """Result from chapter generation."""
    chapter_index: int
    word_count: int
    iterations: int
    final_score: float
    critique_history: List[CritiqueResult] = []
