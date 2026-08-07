"""Value objects - immutable domain values."""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class PhaseStatus(str, Enum):
    """Status of a pipeline phase."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    AWAITING_APPROVAL = "awaiting_approval"


class PipelineStatus(str, Enum):
    """Overall pipeline status."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class CritiqueScore:
    """Immutable critique score."""
    category: str
    score: float  # 1-10
    feedback: str
    weight: float = 1.0

    def weighted_score(self) -> float:
        return self.score * self.weight


@dataclass(frozen=True)
class CritiqueResult:
    """Immutable critique result."""
    scores: tuple  # Tuple of CritiqueScore
    overall_score: float
    passes_threshold: bool
    issues: tuple = ()
    revision_priorities: tuple = ()

    @classmethod
    def from_scores(
        cls,
        scores: List[CritiqueScore],
        threshold: float = 7.0
    ) -> "CritiqueResult":
        """Create from list of scores."""
        if not scores:
            return cls(
                scores=(),
                overall_score=0.0,
                passes_threshold=False
            )

        total_weight = sum(s.weight for s in scores)
        overall = sum(s.weighted_score() for s in scores) / total_weight

        issues = tuple(s.feedback for s in scores if s.score < threshold)
        priorities = tuple(
            s.category for s in sorted(scores, key=lambda x: x.score)[:3]
        )

        return cls(
            scores=tuple(scores),
            overall_score=overall,
            passes_threshold=overall >= threshold,
            issues=issues,
            revision_priorities=priorities
        )


@dataclass(frozen=True)
class GenerationConfig:
    """Configuration for story generation."""
    max_iterations: int = 3
    passing_threshold: float = 7.0
    auto_approve: bool = False
    model_default: str = "sonnet"
    model_prose: str = "opus"
    max_tokens_per_chapter: int = 8000
    temperature: float = 0.7


@dataclass(frozen=True)
class TokenUsage:
    """Token usage tracking."""
    input_tokens: int
    output_tokens: int

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def estimated_cost_usd(self) -> float:
        """Estimate cost based on Claude pricing."""
        # Sonnet pricing: $3/M input, $15/M output
        input_cost = (self.input_tokens / 1_000_000) * 3.0
        output_cost = (self.output_tokens / 1_000_000) * 15.0
        return input_cost + output_cost

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens
        )
