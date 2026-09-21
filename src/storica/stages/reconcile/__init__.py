"""
Stage 6 — Reconcile a finished chapter draft back into canon (DESIGN §5, §8).

Reads: the draft prose + canon + the chapter spec.  Writes: canon (returned, not committed).

This is the stage that killed v1. The old `phase7_consistency` guardian was a one-way ratchet: it
read the prose and *added whatever the prose said* to the story bible. So when the Writer recast the
priest as a creditor (F9), the guardian wrote "Rutz: local creditor" into canon (F10), the next
chapter's reasoner found bible-vs-plan disagreement and invented a bridging fact to smooth it over
(F11), and the reviser then "fixed" the chapter into a far more broken one (F12). One misreading
became permanent, self-propagating truth.

The inversion here is the whole point (principle 1 and 5):

    prose is never truth — facts are EXTRACTED from prose and VALIDATED INTO canon

so every extracted item lands in exactly one of three buckets:

  * **new** — canon has nothing on this key   → promote
  * **consistent** — canon already says this  → ignore (no duplicate, no rewrite)
  * **contradiction** — canon says otherwise  → **flag**, never overwrite

Flagging is the correct terminal behaviour, not a failure: canon and the brief are ground truth, so
a contradiction is adjudicated (DESIGN §6.5) against ground truth — it is never resolved by
letting the draft win, and never by blending both into a new combined fact.

Extraction is **one** structured call (the v1 double extract call is F3 and is deleted), grounded in
the canon slice for exactly what the chapter touches. The same call reports whether each assigned
setup / payoff / promise actually landed in the text, which is what makes the ledger mean something:
a motif the plan says is `paid_off` but that never appeared is a flagged issue, not a status bump.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import List, Optional

from ...canon import Issue, Severity, StoryModel, blocking, validate
from ...llm import StructuredLLM, stage_model
from ...plan import ChapterSpec
from ...trace import Tracer
from .ledger import _update_ledger
from .promote import (
    _promote_aliases,
    _promote_character_facts,
    _promote_knowledge,
    _promote_timeline,
    _promote_world_facts,
)
from .prompts import SYSTEM, _extraction_prompt, reconcile_assignment_block
from .schema import (
    AliasExtract,
    ChapterExtraction,
    CharacterFactExtract,
    ContradictionExtract,
    FactRelation,
    KnowledgeShiftExtract,
    Flag,
    FlagKind,
    LedgerKind,
    LedgerObservation,
    LedgerUpdate,
    Promotion,
    PromotionKind,
    ReconcileFailed,
    ReconcileResult,
    TimelineExtract,
    WorldFactExtract,
)

__all__ = [
    "reconcile_chapter",
    "reconcile_assignment_block",
    "SYSTEM",
    # extraction schema
    "ChapterExtraction", "CharacterFactExtract", "AliasExtract", "WorldFactExtract",
    "TimelineExtract", "ContradictionExtract", "LedgerObservation", "LedgerKind",
    "FactRelation", "KnowledgeShiftExtract",
    # outcomes
    "ReconcileResult", "ReconcileFailed", "Promotion", "PromotionKind",
    "Flag", "FlagKind", "LedgerUpdate",
]


async def reconcile_chapter(
    *,
    chapter: int,
    draft_text: str,
    canon: StoryModel,
    spec: ChapterSpec,
    llm: StructuredLLM,
    tracer: Optional[Tracer] = None,
    model: str = stage_model("reconcile"),
    strict: bool = True,
    max_tokens: int = 16000,
) -> ReconcileResult:
    """
    Extract what chapter `chapter` established, promote what is new, flag what disagrees.

    The returned canon is a *copy*: the canon handed in is never mutated, so a caller that decides
    not to accept the reconcile still holds the untouched original. Nothing is written to disk —
    the pipeline layer decides when to `commit_canon`.
    """
    tracer = tracer or Tracer(None)
    stage = f"ch{chapter:02d}_reconcile"

    prompt = _extraction_prompt(chapter, draft_text, canon, spec)
    extraction = await llm.parse(
        prompt=prompt, schema=ChapterExtraction, system=SYSTEM, model=model, max_tokens=max_tokens
    )
    tracer.record(stage, prompt=prompt, system=SYSTEM, model=model, artifact=extraction)

    working = canon.model_copy(deep=True)
    promoted: List[Promotion] = []
    flagged: List[Flag] = []

    _promote_aliases(working, extraction, promoted, flagged)
    _promote_character_facts(working, extraction, promoted, flagged)
    _promote_world_facts(working, extraction, promoted, flagged)
    _promote_timeline(working, extraction, chapter, promoted, flagged)
    _promote_knowledge(working, extraction, chapter, promoted, flagged)

    for c in extraction.contradictions:
        flagged.append(Flag(
            kind=FlagKind.CONTRADICTION,
            ref=c.canon_ref,
            reason=f"the draft contradicts canon at '{c.canon_ref}' — canon stands until adjudicated",
            canon_says=c.canon_says,
            prose_says=c.prose_says,
            evidence=c.evidence,
        ))

    ledger_updates = _update_ledger(working, extraction, spec, chapter, flagged)

    issues = validate(working)
    issues += [
        Issue(f"reconcile.{f.kind.value}", Severity.WARNING, f.reason, f.ref) for f in flagged
    ]

    result = ReconcileResult(
        canon=working,
        promoted=promoted,
        flagged=flagged,
        ledger_updates=ledger_updates,
        issues=issues,
        extraction=extraction,
    )

    tracer.record(
        f"{stage}_decisions",
        prompt="",
        model=model,
        artifact={
            "promoted": [asdict(p) for p in promoted],
            "flagged": [asdict(f) for f in flagged],
            "ledger_updates": [asdict(u) for u in ledger_updates],
        },
        note=f"{len(promoted)} promoted, {len(flagged)} flagged, {len(ledger_updates)} ledger updates",
    )

    if strict and not result.is_valid:
        raise ReconcileFailed(blocking(issues))
    return result
