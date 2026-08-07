"""
Pipeline entry points for the v2 stages implemented so far.

- `establish_canon` — P2: brief + author → premise → world & cast → validated canon (v1 on disk).
- `plan_macro_arc`  — P3 stage 3: canon → macro arc + the ledger committed into canon (v2 on disk).
- `spec_chapter`    — P3 stage 4: canon + arc → one chapter spec, elaborated just-in-time.

Each is a thin wire-up: load from disk, run the stage, write back. All the judgement lives in the
stages and the checkers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence, Union

from .adjudicator import AdjudicationFailed, Adjudicator, GroundTruth
from .authors import load_author
from .brief import load_brief
from .canon import StoryModel, commit_canon, load_canon, save_canon
from .checkers import (
    AuthorVoiceChecker,
    CanonConsistencyChecker,
    Escalation,
    IntentChecker,
    MicroSenseChecker,
    ProseChecker,
    VitalityChecker,
    with_consensus,
)
from .drafts import load_chapter_draft, load_chapter_draft_if_present, save_chapter_draft
from .llm import StructuredLLM
from .plan import (
    ChapterSpec,
    MacroArc,
    load_chapter_spec_if_present,
    load_macro_arc,
    save_chapter_spec,
    save_macro_arc,
)
from .reports import DecisionLog, DecisionRecord, QuarantineLog, RulingKind
from .stages import (
    Flag,
    FlagKind,
    ProseGateFailed,
    ReconcileResult,
    build_chapter_spec,
    build_macro_arc,
    conceive,
    develop_world_and_cast,
    reconcile_chapter,
    write_chapter,
)
from .trace import Tracer

PathLike = Union[str, Path]

CANON_DIR = "01_canon"
PLAN_DIR = "02_plan"
INPUT_DIR = "00_input"
DRAFTS_DIR = "03_drafts"
TRACE_DIR = "04_trace"
REPORTS_DIR = "05_reports"


def _tracer(novel_dir: Path, trace: bool) -> Tracer:
    return Tracer(novel_dir / TRACE_DIR if trace else None)


async def establish_canon(
    *,
    novel_dir: PathLike,
    authors_root: PathLike,
    llm: StructuredLLM,
    n_candidates: int = 3,
    max_repairs: int = 2,
    conception_model: str = "opus",
    world_cast_model: str = "sonnet",
    trace: bool = True,
) -> StoryModel:
    """Run stages 1–2 for one novel and write the resulting canon."""
    novel_dir = Path(novel_dir)
    brief = load_brief(novel_dir / INPUT_DIR)
    author = load_author(brief.author_id, authors_root)
    tracer = _tracer(novel_dir, trace)

    premise = await conceive(
        brief=brief,
        author=author,
        llm=llm,
        tracer=tracer,
        n_candidates=n_candidates,
        model=conception_model,
    )
    result = await develop_world_and_cast(
        premise=premise,
        brief=brief,
        author=author,
        llm=llm,
        tracer=tracer,
        model=world_cast_model,
        max_repairs=max_repairs,
    )

    save_canon(result.model, novel_dir / CANON_DIR)
    return result.model


async def plan_macro_arc(
    *,
    novel_dir: PathLike,
    authors_root: PathLike,
    llm: StructuredLLM,
    check_intent: bool = True,
    max_repairs: int = 2,
    model: str = "sonnet",
    trace: bool = True,
) -> MacroArc:
    """
    Run stage 3: plan the arc, promote its ledger into canon, and write both.

    The canon commit bumps the version and snapshots to `01_canon/history/`, so the ledger's
    arrival is an auditable canon change like any other.
    """
    novel_dir = Path(novel_dir)
    brief = load_brief(novel_dir / INPUT_DIR)
    author = load_author(brief.author_id, authors_root)
    canon = load_canon(novel_dir / CANON_DIR)
    tracer = _tracer(novel_dir, trace)

    result = await build_macro_arc(
        canon=canon,
        brief=brief,
        author=author,
        llm=llm,
        tracer=tracer,
        intent_checker=IntentChecker(llm, tracer=tracer) if check_intent else None,
        model=model,
        max_repairs=max_repairs,
    )

    commit_canon(result.canon, novel_dir / CANON_DIR)  # ledger is now canon
    save_macro_arc(result.arc, novel_dir / PLAN_DIR)
    return result.arc


async def spec_chapter(
    *,
    novel_dir: PathLike,
    authors_root: PathLike,
    chapter: int,
    llm: StructuredLLM,
    check_intent: bool = True,
    max_repairs: int = 2,
    model: str = "sonnet",
    trace: bool = True,
) -> ChapterSpec:
    """
    Run stage 4 for one chapter, just-in-time.

    Reads canon *as it stands now* — so a chapter specced after chapter 3 has been reconciled sees
    everything chapter 3 established, which is the whole point of elaborating late.
    """
    novel_dir = Path(novel_dir)
    brief = load_brief(novel_dir / INPUT_DIR)
    author = load_author(brief.author_id, authors_root)
    canon = load_canon(novel_dir / CANON_DIR)
    arc = load_macro_arc(novel_dir / PLAN_DIR)
    previous = load_chapter_spec_if_present(novel_dir / PLAN_DIR, chapter - 1) if chapter > 1 else None
    tracer = _tracer(novel_dir, trace)

    result = await build_chapter_spec(
        chapter=chapter,
        canon=canon,
        arc=arc,
        author=author,
        llm=llm,
        previous_spec=previous,
        tracer=tracer,
        intent_checker=IntentChecker(llm, tracer=tracer) if check_intent else None,
        model=model,
        max_repairs=max_repairs,
    )

    save_chapter_spec(result.spec, novel_dir / PLAN_DIR)
    return result.spec


# --------------------------------------------------------------------------------------------
# The chapter loop: spec -> prose -> reconcile, with escalation, adjudication and quarantine
# --------------------------------------------------------------------------------------------


def default_prose_checkers(
    llm: StructuredLLM, tracer: Optional[Tracer] = None, *, samples: int = 3
) -> List[ProseChecker]:
    """
    One reader per failure class (DESIGN §2), cheapest-to-satisfy first.

    Canon-consistency runs before micro-sense and voice because a contradiction makes the other two
    judgements moot: there is no point polishing the texture of a paragraph that says the wrong man
    signed the certificate.

    Vitality runs last, and it is the odd one out: the first three ask whether the prose conforms,
    and it asks whether the prose is alive. Without it a chapter that matches canon, hits its beats
    and sounds like the author passes the whole gate no matter how inert it is — and since repair
    moves prose toward the rubric, that is the chapter this pipeline naturally produces.
    """
    return with_consensus(
        [
            CanonConsistencyChecker(llm, tracer=tracer),
            MicroSenseChecker(llm, tracer=tracer),
            AuthorVoiceChecker(llm, tracer=tracer),
            VitalityChecker(llm, tracer=tracer),
        ],
        samples=samples,
        tracer=tracer,
    )


@dataclass
class ChapterOutcome:
    """What happened to one chapter, including the parts that went badly."""

    chapter: int
    spec: Optional[ChapterSpec] = None
    draft: Optional[str] = None
    reconcile: Optional[ReconcileResult] = None
    rulings: List[DecisionRecord] = field(default_factory=list)
    quarantined: bool = False
    reason: str = ""

    @property
    def unit(self) -> str:
        return f"ch{self.chapter:02d}"


def adjudicator_for(
    novel_dir: Path, llm: StructuredLLM, tracer: Tracer, model: str = "opus"
) -> Adjudicator:
    return Adjudicator(
        llm,
        ground_truth=GroundTruth.load(novel_dir),
        log=DecisionLog(novel_dir / REPORTS_DIR),
        tracer=tracer,
        model=model,
    )


async def draft_chapter(
    *,
    novel_dir: PathLike,
    authors_root: PathLike,
    chapter: int,
    llm: StructuredLLM,
    checkers: Optional[Sequence[ProseChecker]] = None,
    max_repairs: int = 2,
    max_escalations: int = 2,
    model: str = "opus",
    trace: bool = True,
    n_candidates: int = 1,
    samples: int = 3,
) -> ChapterOutcome:
    """
    Write one chapter (stage 5) and survive what goes wrong with it.

    Three outcomes, all of them bounded and none of them a pause (DESIGN D3):
    - it passes its checkers → the draft is written to `03_drafts/`;
    - a checker escalates → the adjudicator rules against immutable ground truth, the ruling is
      logged as binding, and the chapter is re-written *bound by it*. Bounded by `max_escalations`,
      and a re-escalation of the same conflict returns the same ruling rather than looping;
    - the repair budget runs out → the chapter is **quarantined**, not shipped. It is recorded in
      `05_reports/quarantine.jsonl` and excluded from `novel.md`.
    """
    novel_dir = Path(novel_dir)
    brief = load_brief(novel_dir / INPUT_DIR)
    author = load_author(brief.author_id, authors_root)
    canon = load_canon(novel_dir / CANON_DIR)
    arc = load_macro_arc(novel_dir / PLAN_DIR)
    spec = load_chapter_spec_if_present(novel_dir / PLAN_DIR, chapter)
    if spec is None:
        raise FileNotFoundError(f"no spec for chapter {chapter} — run spec_chapter first")

    tracer = Tracer(novel_dir / TRACE_DIR if trace else None)
    quarantine = QuarantineLog(novel_dir / REPORTS_DIR)
    outcome = ChapterOutcome(chapter=chapter, spec=spec)

    previous_draft = load_chapter_draft_if_present(novel_dir / DRAFTS_DIR, chapter - 1)
    previous_tail = (previous_draft or "").strip()[-800:]
    prose_checkers = (
        list(checkers) if checkers is not None else default_prose_checkers(llm, tracer, samples=samples)
    )

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
                checkers=prose_checkers,
                tracer=tracer,
                model=model,
                max_repairs=max_repairs,
                guidance=guidance,
                n_candidates=n_candidates,
            )
        except Escalation as esc:
            if attempt == max_escalations:
                outcome.quarantined = True
                outcome.reason = f"escalated {attempt + 1}x without resolution: {esc.conflict}"
                quarantine.add(outcome.unit, outcome.reason, [esc.conflict])
                return outcome
            try:
                record = await adjudicator_for(novel_dir, llm, tracer).rule(
                    unit=esc.unit, conflict=esc.conflict, context=f"chapter {chapter} prose"
                )
            except AdjudicationFailed as failure:
                outcome.quarantined = True
                outcome.reason = f"adjudication failed: {failure.reason}"
                quarantine.add(outcome.unit, outcome.reason, [esc.conflict])
                return outcome

            outcome.rulings.append(record)
            if record.ruling.kind == RulingKind.AMEND_CANON:
                # Canon amendments are not applied automatically: the ruling is binding and logged,
                # but rewriting canon from a chapter-level conflict is exactly the v1 ratchet. A
                # human or a P5 specialist applies it; the chapter waits.
                outcome.quarantined = True
                outcome.reason = f"ruling requires a canon amendment: {record.ruling.canon_amendment}"
                quarantine.add(outcome.unit, outcome.reason, [esc.conflict])
                return outcome
            guidance = record.ruling.instruction
            continue
        except ProseGateFailed as failed:
            outcome.quarantined = True
            outcome.reason = "prose repair budget exhausted"
            quarantine.add(outcome.unit, outcome.reason, [str(i) for i in failed.issues])
            return outcome

        outcome.draft = result.text
        save_chapter_draft(result.text, novel_dir / DRAFTS_DIR, chapter)
        return outcome

    return outcome


async def reconcile_chapter_into_canon(
    *,
    novel_dir: PathLike,
    chapter: int,
    llm: StructuredLLM,
    model: str = "sonnet",
    adjudicate: bool = True,
    trace: bool = True,
) -> ReconcileResult:
    """
    Run stage 6 and commit the result.

    Contradictions between the draft and canon are **adjudicated, not absorbed**: each one gets a
    binding ruling logged to `decisions.jsonl`, and canon keeps its version of the fact unless the
    adjudicator finds canon itself violates ground truth. This is the inverse of v1's guardian,
    which wrote whatever the prose said into the bible and never looked back (F10).
    """
    novel_dir = Path(novel_dir)
    canon = load_canon(novel_dir / CANON_DIR)
    spec = load_chapter_spec_if_present(novel_dir / PLAN_DIR, chapter)
    if spec is None:
        raise FileNotFoundError(f"no spec for chapter {chapter}")
    draft_text = load_chapter_draft(novel_dir / DRAFTS_DIR, chapter)
    tracer = Tracer(novel_dir / TRACE_DIR if trace else None)

    result = await reconcile_chapter(
        chapter=chapter,
        draft_text=draft_text,
        canon=canon,
        spec=spec,
        llm=llm,
        tracer=tracer,
        model=model,
    )

    if adjudicate:
        await adjudicate_flags(
            novel_dir=novel_dir, chapter=chapter, flags=result.flagged, llm=llm, tracer=tracer
        )

    commit_canon(result.canon, novel_dir / CANON_DIR)
    return result


async def adjudicate_flags(
    *,
    novel_dir: PathLike,
    chapter: int,
    flags: Sequence[Flag],
    llm: StructuredLLM,
    tracer: Optional[Tracer] = None,
    model: str = "opus",
) -> List[DecisionRecord]:
    """
    Rule on the flags that represent a genuine disagreement with canon.

    Only contradictions and name collisions are adjudicated — a missing ledger payoff is a planning
    problem for the next chapter, not a conflict about what is true.
    """
    novel_dir = Path(novel_dir)
    tracer = tracer or Tracer(None)
    adjudicable = {FlagKind.CONTRADICTION, FlagKind.ALIAS_COLLISION}
    records: List[DecisionRecord] = []

    adjudicator = adjudicator_for(novel_dir, llm, tracer, model=model)
    for flag in flags:
        if flag.kind not in adjudicable:
            continue
        conflict = f"{flag.reason} (canon: {flag.canon_says!r}; prose: {flag.prose_says!r})"
        try:
            records.append(await adjudicator.rule(
                unit=f"ch{chapter:02d}:{flag.ref}",
                conflict=conflict,
                context=f"evidence from the draft: {flag.evidence}",
            ))
        except AdjudicationFailed:
            continue  # the flag stays on the record; nothing impermissible becomes binding
    return records
