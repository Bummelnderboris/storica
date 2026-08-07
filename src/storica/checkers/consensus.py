"""
Consensus sampling — turn a flickering judgement into a stable gate.

`calibration/FINDINGS.md` C4 measured what a single draw is worth. Answering the *same* prompt five
times, with nothing varying but sampling:

- on the chapter with five planted contradictions: `revise` in **5/5** draws;
- on the clean control chapter: a blocking issue in **1/5** draws.

So the checker is decisive about real breakage and noisy about clean text. That asymmetry is what
picks the aggregation rule:

| rule | clean text blocked | broken text caught |
|---|---|---|
| single draw (k=1) | ~20% | reliably |
| union over k=3 ("any draw blocks") | **~49%** | reliably |
| **majority over k=3** | **~10%** | reliably |

Union-blocking is the intuitive choice and the wrong one: it multiplies the noise it is trying to
average out, and a pipeline that sends half its good chapters into repair burns its budget re-writing
prose that was already fine — and repair is the step that makes prose grey (§5.1).

Majority is the rule. It costs k calls per checked unit, so it is applied deliberately: to the
checkers whose blocking verdicts are expensive to get wrong, not to everything.

One deliberate asymmetry inside the rule: **the decision is majority, but the issue list is the
union** of every draw that blocked. Once we have decided a unit is broken, we want the repair agent
to see everything anyone found, not only what two readers happened to agree on — a real
contradiction spotted by one careful draw is still a real contradiction.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

from ..authors import AuthorModel
from ..canon import Severity, StoryModel
from ..plan import ChapterSpec, SceneSpec
from ..trace import Tracer
from .base import CheckerIssue, Decision, Verdict
from .prose_base import ProseChecker


def majority_threshold(samples: int) -> int:
    """Strict majority: 2 of 3, 3 of 5, 2 of 2."""
    return samples // 2 + 1


def _dedupe(issues: Sequence[CheckerIssue]) -> List[CheckerIssue]:
    """
    Collapse the same finding reported by different draws.

    Keyed on (canon_ref, unit) rather than on `fix_hint`, because two readers who spot the same
    contradiction phrase the fix differently but point at the same canon id and the same span.
    """
    seen: set[tuple[str, str]] = set()
    out: List[CheckerIssue] = []
    for issue in issues:
        key = (issue.canon_ref.strip().lower(), issue.unit.strip().lower()[:40])
        if key in seen:
            continue
        seen.add(key)
        out.append(issue)
    return out


class ConsensusProseChecker(ProseChecker):
    """
    Wraps any prose checker and runs it `samples` times, blocking only on a majority.

    Transparent by design: it presents the same `check_prose` signature as the checker it wraps, so
    the prose loop needs no knowledge of it and any checker can be sampled without being modified.
    """

    def __init__(
        self,
        inner: ProseChecker,
        *,
        samples: int = 3,
        tracer: Optional[Tracer] = None,
    ):
        if samples < 1:
            raise ValueError("samples must be >= 1")
        self.inner = inner
        self.samples = samples
        self.tracer = tracer or Tracer(None)
        self.name = inner.name

    async def check_prose(
        self,
        *,
        prose: str,
        canon: StoryModel,
        spec: ChapterSpec,
        author: AuthorModel,
        scene: Optional[SceneSpec] = None,
    ) -> Verdict:
        if self.samples == 1:
            return await self.inner.check_prose(
                prose=prose, canon=canon, spec=spec, author=author, scene=scene
            )

        verdicts: List[Verdict] = []
        for _ in range(self.samples):
            verdicts.append(await self.inner.check_prose(
                prose=prose, canon=canon, spec=spec, author=author, scene=scene
            ))

        threshold = majority_threshold(self.samples)
        blocked = [v for v in verdicts if v.blocking_issues()]
        escalated = [v for v in verdicts if v.decision == Decision.ESCALATE]

        unit = f"ch{spec.chapter:02d}" + (f"_{scene.id}" if scene else "")
        self.tracer.record(
            f"consensus_{self.inner.name}_{unit}",
            prompt="",
            artifact={
                "samples": self.samples,
                "threshold": threshold,
                "blocked": len(blocked),
                "escalated": len(escalated),
                "decisions": [v.decision.value for v in verdicts],
            },
            note=f"{len(blocked)}/{self.samples} blocked",
        )

        # Escalation is a claim that canon itself is broken — expensive to act on and expensive to
        # ignore, so it needs the same majority as a block rather than a single alarmed reader.
        if len(escalated) >= threshold:
            return Verdict(
                decision=Decision.ESCALATE,
                summary=f"{len(escalated)}/{self.samples} readers escalated",
                issues=[],
                conflict=next(v.conflict for v in escalated if v.conflict.strip()),
            )

        if len(blocked) >= threshold:
            return Verdict(
                decision=Decision.REVISE,
                summary=f"{len(blocked)}/{self.samples} readers found blocking issues",
                # Union, not intersection: having decided it is broken, repair should see
                # everything anyone found.
                issues=_dedupe([i for v in blocked for i in v.blocking_issues()]),
                conflict="",
            )

        # Below the threshold. Warnings survive — they cost nothing downstream and a minority
        # blocking issue is worth recording as a warning rather than discarding outright.
        minority = [i for v in blocked for i in v.blocking_issues()]
        warnings = [i for v in verdicts for i in v.issues if i not in v.blocking_issues()]
        demoted = [i.model_copy(update={"severity": Severity.WARNING}) for i in _dedupe(minority)]
        return Verdict(
            decision=Decision.PASS,
            summary=f"{len(blocked)}/{self.samples} readers found blocking issues — below majority",
            issues=_dedupe([*warnings, *demoted]),
            conflict="",
        )


def with_consensus(
    checkers: Sequence[ProseChecker],
    *,
    samples: int = 3,
    only: Sequence[str] = ("canon_consistency",),
    tracer: Optional[Tracer] = None,
) -> List[ProseChecker]:
    """
    Sample the named checkers and leave the rest alone.

    Defaults to canon-consistency only: it is the checker whose blocking verdicts were measured, and
    the one whose mistakes are most expensive in both directions — a missed contradiction propagates
    into canon, and a false one sends a good chapter into the loop that flattens it. Sampling
    everything would triple the cost of the whole gate for asymmetries nobody has measured yet.
    """
    names = set(only)
    return [
        ConsensusProseChecker(c, samples=samples, tracer=tracer) if c.name in names else c
        for c in checkers
    ]
