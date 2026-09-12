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

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from ..canon import Issue, Severity
from ..llm import StructuredLLM
from ..trace import Tracer


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
    A checker escalated: the unit cannot be fixed without changing something upstream.

    This is not a crash. `chapter.attempt_chapter` catches it, hands the conflict to the
    `Adjudicator` for a binding ruling against immutable ground truth, and re-attempts the unit
    bound by that ruling. Raising rather than returning is deliberate — an escalation must not be
    mistakeable for a verdict a caller can shrug off, because the alternative is the failure this
    pipeline exists to prevent: a downstream agent inventing a bridging fact (F11/F12).
    """

    def __init__(self, unit: str, conflict: str, verdict: Verdict):
        self.unit = unit
        self.conflict = conflict
        self.verdict = verdict
        super().__init__(f"escalated on {unit}: {conflict}")


class Checker:
    """
    Something that judges a unit against canon and returns a verdict.

    Subclasses supply four class attributes and their own prompt-building methods; the one call
    every checker makes — parse a `Verdict`, then trace it — lives here exactly once. That is not
    only less code: the readers gate every seam in the pipeline, and a gate that behaves slightly
    differently depending on which reader you are looking at is a gate nobody can reason about.

    What a subclass owns is what should differ between readers: `SYSTEM`, its rubric, and how it
    assembles a canon slice and an assignment into a prompt. What it inherits is the machinery.
    """

    #: Stable identity. Prefixes the issue codes this reader produces and its trace records.
    name: str = "checker"
    #: The system prompt this reader is given. Set by every concrete subclass.
    SYSTEM: str = ""
    #: Per-reader call defaults — a whole-book audit needs a bigger budget than a scene check.
    DEFAULT_MODEL: str = "sonnet"
    DEFAULT_MAX_TOKENS: int = 8000
    #: Trace filename prefix; defaults to `<name>_check`.
    TRACE_STAGE: str = ""

    def __init__(
        self,
        llm: StructuredLLM,
        *,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        tracer: Optional[Tracer] = None,
    ):
        if not self.SYSTEM.strip():
            # A reader that forgot its SYSTEM would still return Verdict-shaped answers, so
            # nothing downstream would notice it judging without its role. Fail here instead.
            raise TypeError(f"{type(self).__name__} defines no SYSTEM prompt")
        self.llm = llm
        self.model = model or self.DEFAULT_MODEL
        self.max_tokens = max_tokens or self.DEFAULT_MAX_TOKENS
        self.tracer = tracer or Tracer(None)

    async def check(self, *, prompt: str, unit: str, draw: int = 1) -> Verdict:
        """Judge one unit: one schema-constrained call, recorded to the trace."""
        verdict = await self.llm.parse(
            prompt=prompt,
            schema=Verdict,
            system=self.SYSTEM,
            model=self.model,
            max_tokens=self.max_tokens,
            draw=draw,
        )
        self.tracer.record(
            f"{self.TRACE_STAGE or f'{self.name}_check'}_{unit}",
            prompt=prompt,
            system=self.SYSTEM,
            model=self.model,
            artifact=verdict,
            note=verdict.decision.value,
        )
        return verdict
