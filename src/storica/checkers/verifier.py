"""
The repair verifier — what makes the repair loop converge (DESIGN §6, calibration C7).

The loop used to re-run the whole gate after every repair: fresh readers, full rubric, full text.
That sounds rigorous and is the opposite. A fresh reader is a new draw, and a new draw finds a new
set of issues — so each round the target moved. P6's first chapter shows it exactly: read 1 of
scene 3 filed a date as a *warning* (repair never sees warnings), read 2 made a different detail
blocking, read 3 made the date blocking, and the chapter was quarantined with its budget spent on
three different questions, none of them answered twice. No budget converges against a reader who
re-rolls the question.

So a unit is read in full exactly once. What it is found guilty of is **pinned**, and every repair
after that is checked against the pinned list only:

- was each pinned issue resolved by the edit?
- did the edit itself break something — in the passages it changed, and only there?

Both questions have a fixed answer set, so the open list can only shrink or be replaced by damage the
repair demonstrably did. Two further properties follow for free: a repair round costs one judgement
instead of four to six, and the verifier never sees an unchanged paragraph, so it cannot drift into
re-reviewing the scene.

When the repair did not do what the contract asked — rewrote most of the unit instead of editing
spans — there is no longer a small diff to verify, so `changed_passages` returns None and the caller
falls back to a full re-read. That is the honest fallback: the text really is new.
"""

from __future__ import annotations

import difflib
import re
from typing import List, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field

from ..canon import Issue, Severity
from ..llm import stage_model
from .base import Checker

SYSTEM = """You are the Repair Verifier in an autonomous novel pipeline.

A unit of prose was read by independent readers, who pinned a list of issues. A repair agent was
then told to fix exactly those issues and to change nothing else. You check the repair. You did not
write the prose, you did not find the issues, and you did not make the repair.

You answer two narrow questions and nothing else:
1. For each pinned issue: is it resolved in the repaired text?
2. Did the edit itself introduce a new problem, in the passages it changed?

You are not a reviewer. Do not re-read the unit looking for other faults — you are only shown the
passages that changed, and that is deliberate. A problem that was already there before the repair
is not yours to raise: it was either pinned (question 1) or it was judged acceptable."""

RUBRIC = """How to judge.

Question 1 — resolved or not, per pinned issue:
- RESOLVED when the objection no longer applies to the repaired text. The fix need not be the one
  the issue suggested; cutting the offending span resolves most issues.
- NOT resolved when the objectionable span is still there, or was reworded without removing what
  was objected to.
- If a pinned issue concerns a passage that did not change at all, it is NOT resolved.

Question 2 — introduced problems. Only these count, and only inside the changed passages:
- the edit contradicts the canon slice (a fact, a name, a relationship, who knows what);
- the edit left a sentence that no longer makes sense or no longer follows from its neighbours
  (a dangling reference, a severed transition, a pronoun whose referent was cut);
- the edit replaced a concrete event with a summary or explanation of it;
- the edit is in the wrong language.
Taste is not an introduced problem. A sentence you would have written differently is not one.

Report `introduced` empty unless you can quote the damage."""


class IssueResolution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int = Field(description="The number of the pinned issue, as listed.")
    resolved: bool = Field(description="True only if the objection no longer applies to the repaired text.")
    note: str = Field(description="One short sentence: what the edit did about it.")


class IntroducedProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit: str = Field(description="A quoted span of at most twelve words from a CHANGED passage.")
    kind: str = Field(description="'coherence', 'micro-sense' or 'language'.")
    canon_ref: str = Field(description="The canon id the problem contradicts, or empty.")
    fix_hint: str = Field(description="The smallest edit that removes the damage.")


class RepairCheck(BaseModel):
    """The verifier's answer: one resolution per pinned issue, and any damage the edit did."""

    model_config = ConfigDict(extra="forbid")

    resolutions: List[IssueResolution] = Field(description="Exactly one entry per pinned issue.")
    introduced: List[IntroducedProblem] = Field(
        description="New problems the edit created inside the changed passages. Usually empty."
    )


def _paragraphs(text: str) -> List[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]


#: Past this share of changed paragraphs the repair was a rewrite, not an edit, and there is no
#: diff worth verifying — the caller re-reads the unit in full instead.
REWRITE_SHARE = 0.5


def changed_passages(before: str, after: str) -> Optional[List[tuple[str, str]]]:
    """
    The (before, after) pairs of paragraphs the repair touched, or None if it rewrote the unit.

    An empty list means the repair changed nothing at all.
    """
    old, new = _paragraphs(before), _paragraphs(after)
    matcher = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    pairs: List[tuple[str, str]] = []
    touched = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        touched += max(i2 - i1, j2 - j1)
        pairs.append(("\n\n".join(old[i1:i2]), "\n\n".join(new[j1:j2])))
    if old and touched > REWRITE_SHARE * max(len(old), len(new)):
        return None
    return pairs


def _passages_block(pairs: Sequence[tuple[str, str]]) -> str:
    if not pairs:
        return "(the repair changed nothing — every pinned issue is therefore unresolved)"
    blocks = []
    for n, (old, new) in enumerate(pairs, start=1):
        blocks.append(
            f"## Change {n}\n### Before\n{old or '(nothing — this passage was added)'}\n"
            f"### After\n{new or '(nothing — this passage was cut)'}"
        )
    return "\n\n".join(blocks)


class RepairVerifier(Checker):
    """One call per repair round: were the pinned issues fixed, and did the fix break anything?"""

    name = "repair_verifier"
    SYSTEM = SYSTEM
    DEFAULT_MODEL = stage_model("repair_verifier")
    DEFAULT_MAX_TOKENS = 6000
    TRACE_STAGE = "repair_verify"

    async def verify(
        self,
        *,
        unit: str,
        before: str,
        after: str,
        pinned: Sequence[Issue],
        canon_block: str,
        draw: int = 1,
    ) -> Optional[List[Issue]]:
        """
        The issues still open after this repair, or None when the repair was a rewrite and the unit
        must be re-read in full.
        """
        pairs = changed_passages(before, after)
        if pairs is None:
            return None
        if not pairs:
            return list(pinned)  # nothing changed, so nothing was fixed — no call needed

        listed = "\n".join(f"{n}. {issue}" for n, issue in enumerate(pinned, start=1))
        prompt = f"""{canon_block}

# The pinned issues the repair was told to fix
{listed}

# The passages the repair changed (everything else is byte-identical and not under review)
{_passages_block(pairs)}

{RUBRIC}"""
        check = await self.llm.parse(
            prompt=prompt, schema=RepairCheck, system=self.SYSTEM, model=self.model,
            max_tokens=self.max_tokens, draw=draw,
        )
        self.tracer.record(
            f"{self.TRACE_STAGE}_{unit}", prompt=prompt, system=self.SYSTEM, model=self.model,
            artifact=check,
            note=f"{sum(r.resolved for r in check.resolutions)}/{len(pinned)} resolved, "
                 f"{len(check.introduced)} introduced",
        )

        resolved = {r.index for r in check.resolutions if r.resolved}
        still_open = [issue for n, issue in enumerate(pinned, start=1) if n not in resolved]
        introduced = [
            Issue(
                f"{self.name}.{p.kind}", Severity.BLOCKING,
                f"{p.unit}: introduced by the repair — {p.fix_hint}", p.canon_ref or unit,
            )
            for p in check.introduced
        ]
        return still_open + introduced
