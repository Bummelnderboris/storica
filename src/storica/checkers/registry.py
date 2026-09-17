"""
Who reads what, when, and with how much authority.

Every reader in this package fuses three decisions that have nothing to do with each other:

- **the lens** — the questions it asks and the stance it takes ("you did not write this; canon is
  truth"). That is the checker class itself, and it is the part worth writing carefully.
- **the trigger** — which units it fires on, and how many independent draws it gets.
- **the authority** — whether its findings advise, block a unit, or reach past the unit to the
  adjudicator.

Welding the three together inside each class meant a lens could only ever be used at the one seam
it was written for, and that its power was invisible: you had to read the class to find out whether
its verdict could stop a book. This module separates them. A lens becomes reusable at any seam
(`IntentChecker` reads plans *and* prose), and the gate's policy is one readable table.

The table is policy, so it is argued for here rather than guessed:

- **canon-consistency** is sampled and carries full authority. It is the only reader whose blocking
  rate was measured (calibration C4), and the one whose mistakes cost most in both directions.
- **micro-sense** and **voice** carry full authority but are *not* calibrated. That is a known risk
  (DESIGN §10), not an endorsement.
- **vitality** carries full authority but gates on density rather than presence, which is its own
  form of restraint (calibration C6).
- **intent** on prose is new and uncalibrated, so it *advises*: every finding is recorded, nothing
  is blocked. Vitality is the precedent — it would have flattened the book if it had been given
  teeth before anyone measured it. Promote this row to `Authority.BLOCK` once calibrated.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, List, Optional, Sequence

from ..authors import AuthorModel
from ..canon import Severity, StoryModel
from ..llm import StructuredLLM
from ..plan import ChapterSpec, SceneSpec
from ..trace import Tracer
from .base import Decision, Verdict
from .canon_consistency import CanonConsistencyChecker
from .consensus import ConsensusProseChecker
from .intent import IntentChecker
from .micro_sense import MicroSenseChecker
from .prose_base import ProseChecker
from .vitality import VitalityChecker
from .voice import AuthorVoiceChecker


class Scope(str, Enum):
    """The trigger: which prose units a lens is pointed at."""

    UNIT = "unit"        # every scene, and the assembled chapter
    SCENE = "scene"      # scenes only — a reader whose question is local
    CHAPTER = "chapter"  # the assembled chapter only — a reader whose question is not


class Authority(str, Enum):
    """What a lens is allowed to do with what it finds."""

    ADVISE = "advise"      # findings are recorded as warnings; never blocks, never escalates
    BLOCK = "block"        # blocking findings force a repair; an escalation is demoted to a block
    ESCALATE = "escalate"  # full: may block, and may reach the adjudicator via `Escalation`


LensFactory = Callable[[StructuredLLM, Optional[Tracer]], ProseChecker]


@dataclass(frozen=True)
class ReaderSpec:
    """One row of the gate: a lens, the trigger that fires it, the authority it carries."""

    lens: LensFactory
    scope: Scope = Scope.UNIT
    authority: Authority = Authority.ESCALATE
    #: Draw this reader k times and block only on a majority (`--checker-samples`).
    sampled: bool = False
    #: Why this row is configured the way it is. Read by humans, not by code.
    note: str = ""


def _pass(summary: str, issues=()) -> Verdict:
    return Verdict(decision=Decision.PASS, summary=summary, issues=list(issues), conflict="")


class ScopedProseChecker(ProseChecker):
    """Fires its lens only on the units it is pointed at. Out of scope costs no model call."""

    def __init__(self, inner: ProseChecker, scope: Scope):
        self.inner = inner
        self.scope = scope
        self.name = inner.name

    def fires_on(self, scene: Optional[SceneSpec]) -> bool:
        if self.scope is Scope.SCENE:
            return scene is not None
        if self.scope is Scope.CHAPTER:
            return scene is None
        return True

    async def check_prose(
        self,
        *,
        prose: str,
        canon: StoryModel,
        spec: ChapterSpec,
        author: AuthorModel,
        scene: Optional[SceneSpec] = None,
        draw: int = 1,
    ) -> Verdict:
        if not self.fires_on(scene):
            return _pass(f"{self.name} does not read {'scenes' if scene else 'whole chapters'}")
        return await self.inner.check_prose(
            prose=prose, canon=canon, spec=spec, author=author, scene=scene, draw=draw
        )


class BoundedProseChecker(ProseChecker):
    """
    Caps what a lens may do with what it found. The findings themselves are never discarded.

    `ADVISE` demotes every blocking issue to a warning, so the reader is recorded and costed
    without being able to spend the repair budget. `BLOCK` keeps its teeth on the unit but cannot
    reach upstream: an escalation becomes a blocking issue naming the conflict, because a reader
    that has not been shown the immutable ground truth should not be able to stop the run.
    """

    def __init__(self, inner: ProseChecker, authority: Authority):
        self.inner = inner
        self.authority = authority
        self.name = inner.name

    async def check_prose(self, **kwargs) -> Verdict:
        verdict = await self.inner.check_prose(**kwargs)
        if self.authority is Authority.ESCALATE:
            return verdict
        if self.authority is Authority.BLOCK:
            if verdict.decision != Decision.ESCALATE:
                return verdict
            conflict = verdict.conflict.strip() or verdict.summary
            return verdict.model_copy(update={
                "decision": Decision.REVISE,
                "summary": f"{verdict.summary} [escalation capped: {self.name} may not rule on canon]",
                "issues": [
                    *verdict.issues,
                    _conflict_issue(self.name, conflict, Severity.BLOCKING),
                ],
                "conflict": "",
            })

        demoted = [
            i.model_copy(update={"severity": Severity.WARNING}) if i.severity == Severity.BLOCKING else i
            for i in verdict.issues
        ]
        if verdict.decision == Decision.ESCALATE and verdict.conflict.strip():
            demoted.append(_conflict_issue(self.name, verdict.conflict, Severity.WARNING))
        return verdict.model_copy(update={
            "decision": Decision.PASS,
            "summary": f"{verdict.summary} [advisory: {self.name} records, it does not block]",
            "issues": demoted,
            "conflict": "",
        })


def _conflict_issue(name: str, conflict: str, severity: Severity):
    from .base import CheckerIssue

    return CheckerIssue(
        unit=name, kind="conflict", severity=severity, canon_ref="",
        fix_hint=f"reader reported an upstream conflict it may not rule on: {conflict}",
    )


#: The shipped prose gate. Order matters: canon-consistency first, because a contradiction makes
#: the other judgements moot, and the loop stops there when it blocks. Vitality runs last because
#: it is the only reader asking whether the prose is alive rather than whether it conforms.
PROSE_GATE: Sequence[ReaderSpec] = (
    ReaderSpec(
        lens=lambda llm, tracer: CanonConsistencyChecker(llm, tracer=tracer),
        sampled=True,
        note="the measured reader (C4): a single draw flags clean prose ~20% of the time",
    ),
    ReaderSpec(
        lens=lambda llm, tracer: MicroSenseChecker(llm, tracer=tracer),
        note="uncalibrated and binary-gated — DESIGN §10 risk 1c",
    ),
    ReaderSpec(
        lens=lambda llm, tracer: AuthorVoiceChecker(llm, tracer=tracer),
        note="uncalibrated and binary-gated — DESIGN §10 risk 1c",
    ),
    ReaderSpec(
        lens=lambda llm, tracer: VitalityChecker(llm, tracer=tracer),
        note="gates on issue density, not presence (C6)",
    ),
    ReaderSpec(
        lens=lambda llm, tracer: IntentChecker(llm, tracer=tracer),
        scope=Scope.CHAPTER,
        authority=Authority.ADVISE,
        note="beats are a chapter-scale question; advisory until calibrated (C6's lesson)",
    ),
)


def build_prose_gate(
    llm: StructuredLLM,
    tracer: Optional[Tracer] = None,
    *,
    samples: int = 3,
    table: Sequence[ReaderSpec] = PROSE_GATE,
) -> List[ProseChecker]:
    """Assemble the readers a run uses from the table: lens, then trigger, then authority."""
    readers: List[ProseChecker] = []
    for spec in table:
        reader = spec.lens(llm, tracer)
        if spec.sampled and samples > 1:
            reader = ConsensusProseChecker(reader, samples=samples, tracer=tracer)
        if spec.scope is not Scope.UNIT:
            reader = ScopedProseChecker(reader, spec.scope)
        if spec.authority is not Authority.ESCALATE:
            reader = BoundedProseChecker(reader, spec.authority)
        readers.append(reader)
    return readers
