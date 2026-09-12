"""
One chapter's attempt loop — the bounded state machine around stage 5 (DESIGN §6.5).

This is policy, not wiring, which is why it does not live in `pipeline.py`. Writing a chapter is
the only place in the run where several things can go wrong in different ways, and the rule that
makes the pipeline safe to leave alone is that **none of them is a pause**:

- it passes its checkers                → the draft is returned, and the caller persists it;
- a checker escalates                   → the adjudicator rules against immutable ground truth, the
                                          ruling is logged as binding, and the chapter is re-written
                                          *bound by it*. Bounded by `max_escalations`, and a
                                          re-escalation of the same conflict returns the same ruling
                                          rather than looping (`Adjudicator.rule` consults the log);
- the repair budget runs out            → the chapter is **quarantined**: recorded in
                                          `05_reports/quarantine.jsonl` and excluded from `novel.md`.

Every exit is bounded, logged and visible. Nothing here touches the filesystem except the two logs
it is handed — loading the inputs and saving the draft belong to `pipeline.draft_chapter`, so this
loop can be tested with objects in memory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from .adjudicator import AdjudicationFailed, Adjudicator
from .authors import AuthorModel
from .canon import StoryModel, chapter_unit
from .checkers import Escalation, ProseChecker
from .llm import StructuredLLM, stage_model
from .plan import ChapterSpec, MacroArc
from .reports import DecisionRecord, QuarantineLog, RulingKind
from .stages import ProseGateFailed, write_chapter
from .trace import Tracer


@dataclass
class ChapterOutcome:
    """What happened to one chapter, including the parts that went badly."""

    chapter: int
    spec: Optional[ChapterSpec] = None
    draft: Optional[str] = None
    rulings: List[DecisionRecord] = field(default_factory=list)
    quarantined: bool = False
    reason: str = ""

    @property
    def unit(self) -> str:
        return chapter_unit(self.chapter)


async def attempt_chapter(
    *,
    chapter: int,
    spec: ChapterSpec,
    canon: StoryModel,
    arc: MacroArc,
    author: AuthorModel,
    llm: StructuredLLM,
    adjudicator: Adjudicator,
    quarantine: QuarantineLog,
    checkers: Sequence[ProseChecker],
    tracer: Tracer,
    previous_tail: str = "",
    max_repairs: int = 2,
    max_escalations: int = 2,
    model: str = stage_model("prose"),
    n_candidates: int = 1,
) -> ChapterOutcome:
    """
    Write one chapter and survive what goes wrong with it.

    Returns a `ChapterOutcome` in every case — this function raises nothing. A quarantined outcome
    is a result, not an error: the run is designed to lose a chapter visibly rather than stop.
    """
    outcome = ChapterOutcome(chapter=chapter, spec=spec)

    def quarantined(reason: str, issues: List[str]) -> ChapterOutcome:
        outcome.quarantined = True
        outcome.reason = reason
        quarantine.add(outcome.unit, reason, issues)
        return outcome

    guidance = ""
    for attempt in range(max_escalations + 1):
        try:
            result = await write_chapter(
                spec=spec,
                canon=canon,
                arc=arc,
                author=author,
                llm=llm,
                previous_tail=previous_tail,
                checkers=checkers,
                tracer=tracer,
                model=model,
                max_repairs=max_repairs,
                guidance=guidance,
                n_candidates=n_candidates,
            )
        except ProseGateFailed as failed:
            return quarantined("prose repair budget exhausted", [str(i) for i in failed.issues])
        except Escalation as esc:
            if attempt == max_escalations:
                return quarantined(
                    f"escalated {attempt + 1}x without resolution: {esc.conflict}", [esc.conflict]
                )
            located = "; ".join(f"{i.unit}: {i.fix_hint}" for i in esc.verdict.issues) or "(none located)"
            try:
                record = await adjudicator.rule(
                    unit=esc.unit,
                    conflict=esc.conflict,
                    context=f"chapter {chapter} prose — {esc.verdict.summary}\nissues: {located}",
                )
            except AdjudicationFailed as failure:
                return quarantined(f"adjudication failed: {failure.reason}", [esc.conflict])

            outcome.rulings.append(record)
            if record.ruling.kind == RulingKind.AMEND_CANON:
                # Canon amendments are not applied automatically: the ruling is binding and logged,
                # but rewriting canon from a chapter-level conflict is exactly the v1 ratchet. A
                # human, or a `spawn_specialist` ruling, applies it; the chapter waits.
                return quarantined(
                    f"ruling requires a canon amendment: {record.ruling.canon_amendment}",
                    [esc.conflict],
                )
            # Every ruling so far binds the re-attempt, not only the latest one: a second
            # escalation must not make the chapter forget what the first one settled.
            guidance = "\n".join(g for g in (guidance, record.ruling.instruction) if g)
            continue

        outcome.draft = result.text
        return outcome

    return outcome
