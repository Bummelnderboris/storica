"""Pipeline state management."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import json


class PipelineStatus(str, Enum):
    """Overall pipeline status."""
    NOT_STARTED = "not_started"
    RUNNING = "running"
    PAUSED = "paused"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"


class PhaseStatus(str, Enum):
    """Status of individual phase."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class PhaseState:
    """State of a single pipeline phase."""
    phase_name: str
    status: PhaseStatus = PhaseStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    execution_time_ms: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "phase_name": self.phase_name,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "output": self.output,
            "error": self.error,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "execution_time_ms": self.execution_time_ms
        }


@dataclass
class PipelineState:
    """
    Complete state of a pipeline execution.

    Tracks progress through all phases, costs, and outputs.
    """
    project_id: int
    status: PipelineStatus = PipelineStatus.NOT_STARTED
    current_phase: Optional[str] = None
    phases: Dict[str, PhaseState] = field(default_factory=dict)

    # Accumulated outputs
    topic_exploration: Optional[dict] = None
    story_thesis: Optional[dict] = None
    characters: Optional[dict] = None
    story_architecture: Optional[dict] = None
    story_bible: dict = field(default_factory=dict)

    # Chapter tracking
    current_chapter: int = 0
    total_chapters: int = 0
    chapter_outputs: Dict[int, dict] = field(default_factory=dict)

    # Cost tracking
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    paused_at: Optional[datetime] = None

    # Metadata
    author_id: Optional[str] = None
    author_language: Optional[str] = None

    def start(self) -> None:
        """Mark pipeline as started."""
        self.status = PipelineStatus.RUNNING
        self.started_at = datetime.utcnow()

    def pause(self) -> None:
        """Pause the pipeline."""
        self.status = PipelineStatus.PAUSED
        self.paused_at = datetime.utcnow()

    def resume(self) -> None:
        """Resume the pipeline."""
        self.status = PipelineStatus.RUNNING
        self.paused_at = None

    def complete(self) -> None:
        """Mark pipeline as completed."""
        self.status = PipelineStatus.COMPLETED
        self.completed_at = datetime.utcnow()

    def fail(self, error: str) -> None:
        """Mark pipeline as failed."""
        self.status = PipelineStatus.FAILED
        self.completed_at = datetime.utcnow()
        if self.current_phase and self.current_phase in self.phases:
            self.phases[self.current_phase].error = error
            self.phases[self.current_phase].status = PhaseStatus.FAILED

    def start_phase(self, phase_name: str) -> PhaseState:
        """Start a new phase."""
        self.current_phase = phase_name
        phase_state = PhaseState(
            phase_name=phase_name,
            status=PhaseStatus.RUNNING,
            started_at=datetime.utcnow()
        )
        self.phases[phase_name] = phase_state
        return phase_state

    def complete_phase(
        self,
        phase_name: str,
        output: dict,
        input_tokens: int = 0,
        output_tokens: int = 0,
        execution_time_ms: int = 0
    ) -> None:
        """Mark a phase as completed."""
        if phase_name in self.phases:
            phase = self.phases[phase_name]
            phase.status = PhaseStatus.COMPLETED
            phase.completed_at = datetime.utcnow()
            phase.output = output
            phase.input_tokens = input_tokens
            phase.output_tokens = output_tokens
            phase.execution_time_ms = execution_time_ms

            # Update totals
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens

    def await_approval(self, phase_name: str) -> None:
        """Mark phase as awaiting approval."""
        if phase_name in self.phases:
            self.phases[phase_name].status = PhaseStatus.AWAITING_APPROVAL
        self.status = PipelineStatus.AWAITING_APPROVAL

    def approve_phase(self, phase_name: str) -> None:
        """Approve a phase."""
        if phase_name in self.phases:
            self.phases[phase_name].status = PhaseStatus.APPROVED
        self.status = PipelineStatus.RUNNING

    def reject_phase(self, phase_name: str, reason: str) -> None:
        """Reject a phase."""
        if phase_name in self.phases:
            self.phases[phase_name].status = PhaseStatus.REJECTED
            self.phases[phase_name].error = reason

    def get_cost_estimate(self) -> dict:
        """Get current cost estimate."""
        # Approximate pricing (Claude Sonnet)
        input_cost_per_1k = 0.003
        output_cost_per_1k = 0.015

        input_cost = (self.total_input_tokens / 1000) * input_cost_per_1k
        output_cost = (self.total_output_tokens / 1000) * output_cost_per_1k

        return {
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "estimated_cost_usd": round(input_cost + output_cost, 4)
        }

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "project_id": self.project_id,
            "status": self.status.value,
            "current_phase": self.current_phase,
            "phases": {k: v.to_dict() for k, v in self.phases.items()},
            "current_chapter": self.current_chapter,
            "total_chapters": self.total_chapters,
            "cost": self.get_cost_estimate(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "author_id": self.author_id,
            "author_language": self.author_language
        }

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, data: dict) -> "PipelineState":
        """Create from dictionary."""
        state = cls(project_id=data["project_id"])
        state.status = PipelineStatus(data.get("status", "not_started"))
        state.current_phase = data.get("current_phase")
        state.current_chapter = data.get("current_chapter", 0)
        state.total_chapters = data.get("total_chapters", 0)
        state.author_id = data.get("author_id")
        state.author_language = data.get("author_language")

        # Restore phases
        for name, phase_data in data.get("phases", {}).items():
            state.phases[name] = PhaseState(
                phase_name=name,
                status=PhaseStatus(phase_data.get("status", "pending")),
                output=phase_data.get("output"),
                error=phase_data.get("error"),
                input_tokens=phase_data.get("input_tokens", 0),
                output_tokens=phase_data.get("output_tokens", 0),
                execution_time_ms=phase_data.get("execution_time_ms", 0)
            )

        # Restore cost tracking
        cost = data.get("cost", {})
        state.total_input_tokens = cost.get("input_tokens", 0)
        state.total_output_tokens = cost.get("output_tokens", 0)

        return state
