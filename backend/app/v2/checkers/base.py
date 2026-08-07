"""
The verification layer's shared vocabulary (DESIGN §6).

Every checker is a **fresh agent**: it gets the unit, the exact canon slice it must respect, and a
rubric — and nothing from the generation that produced the unit. Our LLM calls are stateless, so
freshness is structural here, not a discipline someone has to remember.

A checker never returns a score. It returns a **verdict with an issue list**, and the loop fires
repair when *any* issue is blocking. That is the deliberate opposite of v1's weighted-average gate,
which competent-but-hollow drafts always passed (F8).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import List

from pydantic import BaseModel, ConfigDict, Field

from ..canon import Issue, Severity


class Decision(str, Enum):
    PASS = "pass"
    REVISE = "revise"      # fixable in place, against canon
    ESCALATE = "escalate"  # cannot be fixed locally — adjudication required (§6.5)


class CheckerIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit: str = Field(description="The part of the unit at fault, e.g. a beat id, scene id, chapter number.")
    kind: str = Field(description="What kind of failure: 'intent', 'meaning', 'coherence', or 'micro-sense'.")
    severity: Severity = Field(description="'blocking' if the unit cannot proceed as-is, otherwise 'warning'.")
    canon_ref: str = Field(description="The canon or plan id this judgement is grounded in. Empty if none.")
    fix_hint: str = Field(description="The smallest change that resolves it. Never 'rewrite it'.")


class Verdict(BaseModel):
    """A checker's ruling on one unit."""

    model_config = ConfigDict(extra="forbid")

    decision: Decision
    summary: str = Field(description="One sentence: what this unit does, and whether it earns its place.")
    issues: List[CheckerIssue] = Field(description="Every issue found. Empty when the decision is 'pass'.")
    conflict: str = Field(
        description="Only when escalating: the conflict that cannot be resolved without changing "
        "something upstream. Empty otherwise."
    )

    def blocking_issues(self) -> List[CheckerIssue]:
        return [i for i in self.issues if i.severity == Severity.BLOCKING]

    def to_issues(self, prefix: str) -> List[Issue]:
        """Convert to canon `Issue`s so deterministic and LLM findings flow through one repair loop."""
        return [
            Issue(f"{prefix}.{i.kind}", i.severity, f"{i.unit}: {i.fix_hint}", i.canon_ref or i.unit)
            for i in self.issues
        ]


class Escalation(RuntimeError):
    """
    A checker escalated. Until P5's adjudicator exists, this stops the run loudly rather than
    letting a downstream agent invent a bridging fact to paper over the conflict (F11/F12).
    """

    def __init__(self, unit: str, conflict: str, verdict: Verdict):
        self.unit = unit
        self.conflict = conflict
        self.verdict = verdict
        super().__init__(f"escalated on {unit}: {conflict}")


class Checker(ABC):
    """Marker base: something that judges a unit against canon and returns a verdict."""

    name: str = "checker"

    @abstractmethod
    async def check(self, *args, **kwargs) -> Verdict:
        """Judge one unit."""
