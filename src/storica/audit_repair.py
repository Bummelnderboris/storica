"""
Acting on the final audit (DESIGN §6.5, §6.6).

The final auditor is the only reader that sees the whole book, and so the only one that can find a
contradiction *between* chapters — a detail stated one way in chapter 1 and another in chapter 3,
each chapter clean on its own. For a long time its verdict was reported and nothing happened: the
run ended "not done" with the fix written out in `run_report.json`. P6's first complete book ended
exactly there, with eight such findings.

This module is the missing leg. Each blocking audit finding is routed to ONE chapter and repaired
there through the same contract as every other repair — fix the named spans, change nothing else,
invent no fact — and the repair is checked by the repair verifier against the finding and a diff.

Routing is the part worth arguing for. A finding like `ch01 vs ch03` names two chapters; repairing
both would move both sides of a contradiction and can create a new one. So exactly one side moves:

- the chapter the fix hint names, when it names exactly one;
- otherwise the **later** chapter. The earlier chapter was reconciled into canon before the later one
  was written against it, so the earlier side is what canon already holds and the later side is the
  one that drifted.

A repair that rewrites the chapter instead of editing it is rejected, not verified: a chapter under
audit repair has already passed its full gate once, and a rewrite would put unread text into the
book at the very last step.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from .canon import Issue, Severity, StoryModel
from .checkers.base import CheckerIssue, Verdict
from .checkers.verifier import RepairVerifier, changed_passages
from .llm import StructuredLLM, stage_model
from .plan import ChapterSpec
from .stages.prose.prompts import (
    MIN_SCENE_CHARS,
    SYSTEM as PROSE_SYSTEM,
    _chapter_slice,
    _language,
    _repair_prompt,
)
from .stages.prose.quality import _deterministic_issues
from .trace import Tracer

_CHAPTER = re.compile(r"\bch(?:apter|apitel)?\s*0*(\d+)\b", re.IGNORECASE)


def _chapters_in(text: str) -> List[int]:
    return [int(n) for n in _CHAPTER.findall(text or "")]


def route(issue: CheckerIssue, known: Sequence[int]) -> Optional[int]:
    """The one chapter a blocking audit finding is repaired in, or None if it names none we have."""
    named = [n for n in dict.fromkeys(_chapters_in(issue.unit)) if n in known]
    hinted = [n for n in dict.fromkeys(_chapters_in(issue.fix_hint)) if n in known]
    if len(hinted) == 1:
        return hinted[0]
    if named:
        return max(named)
    return hinted[0] if hinted else None


@dataclass
class AuditRepairResult:
    """What one round of audit repair did, chapter by chapter."""

    texts: Dict[int, str] = field(default_factory=dict)       # chapter -> repaired text (changed only)
    unresolved: List[str] = field(default_factory=list)        # findings still open after the round
    unrouted: List[str] = field(default_factory=list)          # findings naming no chapter we have


async def repair_from_audit(
    *,
    verdict: Verdict,
    drafts: Dict[int, str],
    specs: Dict[int, ChapterSpec],
    canon: StoryModel,
    llm: StructuredLLM,
    tracer: Optional[Tracer] = None,
    max_repairs: int = 2,
    model: str = stage_model("prose"),
    max_tokens: int = 32000,
) -> AuditRepairResult:
    """
    Repair each chapter the audit's blocking findings route to. Returns the changed texts; the
    caller saves them together, so a run that pauses mid-round leaves every draft untouched.
    """
    tracer = tracer or Tracer(None)
    verifier = RepairVerifier(llm, tracer=tracer)
    result = AuditRepairResult()

    by_chapter: Dict[int, List[Issue]] = {}
    for finding in verdict.blocking_issues():
        chapter = route(finding, list(drafts))
        if chapter is None:
            result.unrouted.append(f"{finding.unit}: {finding.fix_hint}")
            continue
        by_chapter.setdefault(chapter, []).append(Issue(
            f"final_auditor.{finding.kind}", Severity.BLOCKING,
            f"{finding.unit}: {finding.fix_hint}", finding.canon_ref or finding.unit,
        ))

    language = _language(canon)
    for chapter in sorted(by_chapter):
        unit = f"ch{chapter:02d}"
        text = drafts[chapter]
        canon_block = _chapter_slice(specs[chapter], canon)
        pinned = by_chapter[chapter]

        for round_ in range(1, max_repairs + 1):
            if not pinned:
                break
            prompt = _repair_prompt(
                unit=f"chapter {chapter}", current=text, issues=pinned,
                canon_block=canon_block, language=language, regenerate_prompt="",
            )
            repaired = await llm.generate(
                prompt=prompt, system=PROSE_SYSTEM, model=model, max_tokens=max_tokens, draw=round_,
            )
            tracer.record(
                f"{unit}_prose_audit_repair_{round_}", prompt=prompt, system=PROSE_SYSTEM,
                model=model, artifact=repaired, note=f"{len(pinned)} audit finding(s)",
            )
            if _deterministic_issues(repaired, unit, MIN_SCENE_CHARS) or changed_passages(text, repaired) is None:
                continue  # a stub or a rewrite: keep the chapter that passed its gate, try again
            still_open = await verifier.verify(
                unit=f"{unit}_audit", before=text, after=repaired, pinned=pinned,
                canon_block=canon_block, draw=round_,
            )
            text = repaired
            pinned = still_open or []

        if text != drafts[chapter]:
            result.texts[chapter] = text
        result.unresolved += [str(i) for i in pinned]

    return result
