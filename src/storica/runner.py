"""
The run loop: brief in, novel out (DESIGN §9, P6).

`run_novel` walks every stage in order and is **resumable by construction**: each step asks the
filesystem whether its artifact already exists and skips it if so. That matters for two reasons —
an autonomous run that dies at chapter 7 resumes at chapter 7, and a run driven by `ReplayLLM`
(no API key, answers written by hand) stops on *every* unanswered call and must pick up exactly
where it left off, hundreds of times, without redoing work.

Progress lives in the artifacts themselves rather than in a status file, with one exception:
whether a chapter has been reconciled is not visible from the files alone, so `05_reports/state.json`
records it. Everything else is inferred from `01_canon/`, `02_plan/`, `03_drafts/`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence, Union

from .adjudicator import AdjudicationFailed
from .assembly import assemble_novel, save_novel
from .canon import load_canon
from .checkers import Decision, FinalAuditor, ProseChecker
from .drafts import drafted_chapters
from .llm import StructuredLLM
from .plan import load_macro_arc, macro_arc_path, specced_chapters
from .pipeline import (
    CANON_DIR,
    DRAFTS_DIR,
    PLAN_DIR,
    REPORTS_DIR,
    TRACE_DIR,
    adjudicator_for,
    draft_chapter,
    establish_canon,
    plan_macro_arc,
    reconcile_chapter_into_canon,
    spec_chapter,
)
from .reports import QuarantineLog, write_run_report
from .trace import Tracer

PathLike = Union[str, Path]

STATE_FILE = "state.json"


@dataclass
class RunState:
    """The one bit of progress the filesystem cannot tell us: which chapters were reconciled."""

    reconciled: List[int] = field(default_factory=list)

    @classmethod
    def load(cls, reports_dir: Path) -> "RunState":
        path = reports_dir / STATE_FILE
        if not path.exists():
            return cls()
        return cls(**json.loads(path.read_text(encoding="utf-8")))

    def save(self, reports_dir: Path) -> None:
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / STATE_FILE).write_text(
            json.dumps({"reconciled": sorted(self.reconciled)}, indent=2), encoding="utf-8"
        )


@dataclass
class RunResult:
    novel_path: Optional[Path]
    chapters: List[int] = field(default_factory=list)
    quarantined: List[str] = field(default_factory=list)
    audit_summary: str = ""
    audit_decision: str = ""
    audit_issues: List[str] = field(default_factory=list)
    audit_ruling: str = ""

    @property
    def is_done(self) -> bool:
        """A book is finished only when nothing was quarantined and the audit passed (§6.5)."""
        return (
            self.novel_path is not None
            and not self.quarantined
            and self.audit_decision in ("", "pass")
        )


async def run_novel(
    *,
    novel_dir: PathLike,
    authors_root: PathLike,
    llm: StructuredLLM,
    checkers: Optional[Sequence[ProseChecker]] = None,
    audit: bool = True,
    reconcile: bool = True,
    check_intent: bool = True,
    max_repairs: int = 2,
    trace: bool = True,
    n_candidates: int = 1,
) -> RunResult:
    """
    Run the whole pipeline for one novel, skipping any stage whose artifact already exists.

    The creator touches the front door only (D3): a brief in `00_input/`. Everything after that —
    conception, cast, arc, specs, prose, reconciliation, adjudication, assembly, audit — happens
    without a pause, and every decision it made is on disk afterwards.
    """
    novel_dir = Path(novel_dir)
    reports_dir = novel_dir / REPORTS_DIR
    state = RunState.load(reports_dir)

    # Stages 1-2 — canon. Ground truth is locked the moment this commits.
    if not (novel_dir / CANON_DIR / "story_model.json").exists():
        await establish_canon(
            novel_dir=novel_dir, authors_root=authors_root, llm=llm,
            max_repairs=max_repairs, trace=trace,
        )

    # Stage 3 — the macro arc, and the ledger into canon.
    if not macro_arc_path(novel_dir / PLAN_DIR).exists():
        await plan_macro_arc(
            novel_dir=novel_dir, authors_root=authors_root, llm=llm,
            check_intent=check_intent, max_repairs=max_repairs, trace=trace,
        )

    arc = load_macro_arc(novel_dir / PLAN_DIR)
    quarantine = QuarantineLog(reports_dir)

    for chapter in range(1, arc.chapter_count + 1):
        unit = f"ch{chapter:02d}"
        if quarantine.is_quarantined(unit):
            continue

        # Stage 4 — the spec, elaborated just-in-time from canon as it stands NOW, so it inherits
        # everything the previous chapters reconciled.
        if chapter not in specced_chapters(novel_dir / PLAN_DIR):
            await spec_chapter(
                novel_dir=novel_dir, authors_root=authors_root, chapter=chapter, llm=llm,
                check_intent=check_intent, max_repairs=max_repairs, trace=trace,
            )

        # Stage 5 — prose.
        if chapter not in drafted_chapters(novel_dir / DRAFTS_DIR):
            outcome = await draft_chapter(
                novel_dir=novel_dir, authors_root=authors_root, chapter=chapter, llm=llm,
                checkers=checkers, max_repairs=max_repairs, trace=trace,
                n_candidates=n_candidates,
            )
            if outcome.quarantined:
                continue

        # Stage 6 — reconcile the draft back into canon.
        if reconcile and chapter not in state.reconciled:
            await reconcile_chapter_into_canon(
                novel_dir=novel_dir, chapter=chapter, llm=llm, trace=trace
            )
            state.reconciled.append(chapter)
            state.save(reports_dir)

    # Assembly — quarantined chapters are excluded rather than shipped.
    canon = load_canon(novel_dir / CANON_DIR)
    assembled = assemble_novel(
        canon=canon, arc=arc, drafts_dir=novel_dir / DRAFTS_DIR, quarantine=quarantine
    )
    novel_path = save_novel(assembled.text, novel_dir) if assembled.text.strip() else None

    result = RunResult(
        novel_path=novel_path,
        chapters=assembled.chapters,
        quarantined=quarantine.units(),
    )

    # The last gate: one fresh reader on the whole book (§6.5).
    if audit and novel_path is not None:
        tracer = Tracer(novel_dir / TRACE_DIR if trace else None)
        verdict = await FinalAuditor(llm, tracer=tracer).audit(
            novel_text=assembled.text, canon=canon, arc=arc, quarantined=quarantine.units()
        )
        result.audit_summary = verdict.summary
        result.audit_decision = verdict.decision.value
        result.audit_issues = [str(i) for i in verdict.to_issues("final_auditor")]

        # The auditor is the last agent that can find canon incoherent. If it does, that conflict
        # gets a binding ruling like any other rather than being reported and forgotten.
        if verdict.decision == Decision.ESCALATE and verdict.conflict.strip():
            try:
                record = await adjudicator_for(novel_dir, llm, tracer).rule(
                    unit="novel", conflict=verdict.conflict, context="raised by the final audit"
                )
                result.audit_ruling = record.ruling.binding_summary
            except AdjudicationFailed as failure:
                result.audit_ruling = f"adjudication failed: {failure.reason}"

    write_run_report(reports_dir, {
        "chapters_included": assembled.chapters,
        "chapters_excluded": assembled.excluded,
        "quarantined": quarantine.units(),
        "assembly_issues": [str(i) for i in assembled.issues],
        "audit_decision": result.audit_decision,
        "audit_summary": result.audit_summary,
        "audit_issues": result.audit_issues,
        "audit_ruling": result.audit_ruling,
        "canon_version": canon.version,
        "is_done": result.is_done,
    })
    return result
