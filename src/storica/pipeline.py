"""
Pipeline entry points: load from disk, run the stage, write back.

- `establish_canon`             — stages 1–2: brief + author → premise → world & cast → canon v1.
- `plan_macro_arc`              — stage 3: canon → macro arc + the ledger committed into canon.
- `spec_chapter`                — stage 4: canon + arc → one chapter spec, elaborated just-in-time.
- `draft_chapter`               — stage 5: the inputs and the saved draft around `attempt_chapter`.
- `reconcile_chapter_into_canon`— stage 6, and the adjudication of what it flagged.

Every function here is I/O. The judgement lives in `stages/` and `checkers/`; the decision tree for
a chapter that goes wrong lives in `chapter.py`; this module only moves things on and off disk.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Sequence, Union

from .adjudicator import AdjudicationFailed, Adjudicator, GroundTruth
from .authors import load_author
from .brief import load_brief
from .canon import Issue, Severity, StoryModel, commit_canon, load_canon, save_canon
from .chapter import ChapterOutcome, attempt_chapter
from .checkers import IntentChecker, ProseChecker, default_prose_checkers
from .drafts import load_chapter_draft, load_chapter_draft_if_present, save_chapter_draft
from .llm import StructuredLLM, stage_model
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
    ReconcileResult,
    build_chapter_spec,
    build_macro_arc,
    conceive,
    develop_world_and_cast,
    reconcile_chapter,
)
from .stages.prose import MIN_SCENE_CHARS, SYSTEM as PROSE_SYSTEM, TAIL_CHARS
from .stages.prose.prompts import _chapter_slice, _language, _repair_prompt
from .stages.prose.quality import _deterministic_issues
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
    conception_model: str = stage_model("conception"),
    world_cast_model: str = stage_model("world_cast"),
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
    model: str = stage_model("macro_arc"),
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
    model: str = stage_model("chapter_spec"),
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


def adjudicator_for(
    novel_dir: Path, llm: StructuredLLM, tracer: Tracer, model: str = stage_model("adjudicator")
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
    model: str = stage_model("prose"),
    trace: bool = True,
    n_candidates: int = 1,
    samples: int = 3,
) -> ChapterOutcome:
    """
    Run stage 5 for one chapter: load its inputs, attempt it, persist the draft if it survived.

    The attempt loop itself — escalate, adjudicate, retry, quarantine — is `chapter.attempt_chapter`.
    This function is the disk around it.
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
    previous_draft = load_chapter_draft_if_present(novel_dir / DRAFTS_DIR, chapter - 1)

    outcome = await attempt_chapter(
        chapter=chapter,
        spec=spec,
        canon=canon,
        arc=arc,
        author=author,
        llm=llm,
        adjudicator=adjudicator_for(novel_dir, llm, tracer),
        quarantine=QuarantineLog(novel_dir / REPORTS_DIR),
        checkers=(
            list(checkers) if checkers is not None
            else default_prose_checkers(llm, tracer, samples=samples)
        ),
        tracer=tracer,
        # How much of the previous chapter rides into the next one, to inherit its rhythm without
        # the model continuing a paragraph instead of opening a chapter.
        previous_tail=(previous_draft or "").strip()[-TAIL_CHARS:],
        max_repairs=max_repairs,
        max_escalations=max_escalations,
        model=model,
        n_candidates=n_candidates,
    )

    if outcome.draft is not None:
        save_chapter_draft(outcome.draft, novel_dir / DRAFTS_DIR, chapter)
    return outcome


async def reconcile_chapter_into_canon(
    *,
    novel_dir: PathLike,
    chapter: int,
    llm: StructuredLLM,
    model: str = stage_model("reconcile"),
    adjudicate: bool = True,
    trace: bool = True,
) -> ReconcileResult:
    """
    Run stage 6, act on what was ruled, and commit the result.

    Contradictions between the draft and canon are **adjudicated, not absorbed**: each one gets a
    binding ruling logged to `decisions.jsonl`. Canon keeps its version of the fact in every case.
    This is the inverse of v1's guardian, which wrote whatever the prose said into the bible and
    never looked back (F10). What a ruling then *does*:

    - `correct_the_unit` — the saved draft gets one grounded repair pass bound by the ruling's
      instruction and is re-saved. (The checkers passed this prose before the reconciler
      disagreed with it; the ruling, not the reconciler, is what makes the draft wrong.)
    - `amend_canon` — canon is never rewritten from a chapter-level conflict (the v1 ratchet), so
      the chapter is quarantined for a human to apply the amendment, and **nothing** from it is
      committed: an excluded chapter must not leave facts behind in canon.
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
        records = await adjudicate_flags(
            novel_dir=novel_dir, chapter=chapter, flags=result.flagged, llm=llm, tracer=tracer
        )
        amendments = [r for r in records if r.ruling.kind == RulingKind.AMEND_CANON]
        if amendments:
            QuarantineLog(novel_dir / REPORTS_DIR).add(
                f"ch{chapter:02d}",
                "reconcile ruling requires a canon amendment",
                [f"{r.conflict} -> {r.ruling.canon_amendment}" for r in amendments],
            )
            return result  # canon deliberately NOT committed
        corrections = [r for r in records if r.ruling.kind == RulingKind.CORRECT_UNIT]
        if corrections:
            await correct_draft_by_ruling(
                novel_dir=novel_dir, chapter=chapter, canon=canon, spec=spec,
                records=corrections, llm=llm, tracer=tracer,
            )

    commit_canon(result.canon, novel_dir / CANON_DIR)
    return result


async def correct_draft_by_ruling(
    *,
    novel_dir: PathLike,
    chapter: int,
    canon: StoryModel,
    spec: ChapterSpec,
    records: Sequence[DecisionRecord],
    llm: StructuredLLM,
    tracer: Optional[Tracer] = None,
    model: str = stage_model("prose"),
    max_tokens: int = 32000,
) -> str:
    """
    One grounded repair of the saved draft, bound by the rulings that found it wrong.

    Uses the same repair contract as the prose gate — fix what is named, change nothing else,
    invent no fact — with each ruling's instruction as the issue to fix. A repair that comes back
    as a stub is discarded and the previous draft kept, so a bad call cannot blank a chapter.
    """
    novel_dir = Path(novel_dir)
    tracer = tracer or Tracer(None)
    unit = f"ch{chapter:02d}"
    current = load_chapter_draft(novel_dir / DRAFTS_DIR, chapter)
    issues = [
        Issue(
            "ruling.correct_the_unit", Severity.BLOCKING,
            f"{r.ruling.instruction} (binding: {r.ruling.binding_summary})", r.unit,
        )
        for r in records
    ]
    prompt = _repair_prompt(
        unit=f"chapter {chapter}", current=current, issues=issues,
        canon_block=_chapter_slice(spec, canon), language=_language(canon), regenerate_prompt="",
    )
    text = await llm.generate(prompt=prompt, system=PROSE_SYSTEM, model=model, max_tokens=max_tokens)
    stub = _deterministic_issues(text, unit, MIN_SCENE_CHARS)
    tracer.record(
        f"{unit}_prose_ruling_repair", prompt=prompt, system=PROSE_SYSTEM, model=model,
        artifact=text,
        note=f"{len(records)} binding ruling(s)" + ("; repair discarded as a stub" if stub else ""),
    )
    if stub:
        return current
    save_chapter_draft(text, novel_dir / DRAFTS_DIR, chapter)
    return text


async def adjudicate_flags(
    *,
    novel_dir: PathLike,
    chapter: int,
    flags: Sequence[Flag],
    llm: StructuredLLM,
    tracer: Optional[Tracer] = None,
    model: str = stage_model("adjudicator"),
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
