"""
Stage 3 — Macro-arc (DESIGN §5).

Reads: the full canon.  Writes: `02_plan/macro_arc.json` **and the meaning ledger into canon**.

Everything is expressed by id: beats name character ids, the ledger names motif/promise ids. That
is what lets the Intent checker ask a question v1 could not — "did this unit advance the beat it
was *assigned*?" — instead of scoring prose quality and calling it meaning (F8).

The motif/promise schedule is promoted into `canon.motifs` / `canon.promises` with status
`planned` / `open`, because the ledger's home is canon (§4). The stored arc keeps only their ids,
so the schedule can never be restated into disagreement with the canon it came from.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from ..authors import AuthorModel
from ..brief import Brief
from ..canon import (
    Issue,
    Motif,
    MotifStatus,
    Promise,
    PromiseStatus,
    StoryModel,
    blocking,
    canon_slice,
    validate,
)
from ..checkers import Escalation, IntentChecker
from ..checkers.base import Decision
from ..llm import StructuredLLM
from ..plan import MacroArc, MacroArcDraft, validate_macro_arc_draft
from ..trace import Tracer
from .gate import GateFailed, format_issues, run_gated

SYSTEM = """You are the Macro-arc agent of an autonomous novel pipeline.

You plan the whole book's movement — acts, turning points, per-character beats, the motif and
promise schedule, the tension curve. You do not write prose and you do not restate canon: every
character, motif and promise is referenced by ID.

Your plan is checked mechanically and then read by an Intent checker that asks whether each unit
earns its place. A chapter that carries no beat, no turn and no ledger event will be rejected."""


class MacroArcGateFailed(GateFailed):
    """The macro arc still had blocking issues when the repair budget ran out."""


@dataclass
class MacroArcResult:
    arc: MacroArc
    canon: StoryModel  # canon with the ledger promoted — caller commits it
    issues: List[Issue] = field(default_factory=list)
    repairs: int = 0

    @property
    def is_valid(self) -> bool:
        return not blocking(self.issues)


def promote_ledger(canon: StoryModel, draft: MacroArcDraft) -> StoryModel:
    """Write the arc's motif/promise schedule into canon as a ledger of planned/open entries."""
    motifs = [
        Motif(id=m.id, desc=m.desc, setup_ch=m.setup_ch, payoff_ch=m.payoff_ch, status=MotifStatus.PLANNED)
        for m in draft.motifs
    ]
    promises = [
        Promise(
            id=p.id,
            desc=p.desc,
            made_ch=p.made_ch,
            kept_ch=p.kept_ch or None,  # 0 means deliberately unresolved
            status=PromiseStatus.OPEN,
        )
        for p in draft.promises
    ]
    return canon.model_copy(update={"motifs": motifs, "promises": promises})


def to_macro_arc(draft: MacroArcDraft) -> MacroArc:
    """Strip the inline ledger; keep the ids. Canon owns the definitions from here on."""
    return MacroArc(
        chapter_count=draft.chapter_count,
        shape=draft.shape,
        acts=draft.acts,
        turning_points=draft.turning_points,
        arc_beats=draft.arc_beats,
        motif_ids=[m.id for m in draft.motifs],
        promise_ids=[p.id for p in draft.promises],
        tension_curve=draft.tension_curve,
    )


def _key(issue: Issue) -> tuple:
    return (issue.code, issue.ref, issue.message)


def _new_issues(base: List[Issue], current: List[Issue]) -> List[Issue]:
    """Issues the ledger promotion introduced — pre-existing canon warnings are not this stage's."""
    seen = {_key(i) for i in base}
    return [i for i in current if _key(i) not in seen]


def _draft_prompt(canon: StoryModel, brief: Brief, author: AuthorModel) -> str:
    chapters = canon.constraints.chapter_count
    target = f"exactly {chapters} chapters" if chapters else "as many chapters as the story needs (8-15 is typical)"
    return f"""{canon_slice(canon)}

{author.conception_block()}

{brief.prompt_block()}

## Task
Plan the macro arc of this novel in {target}.

Structural rules (checked mechanically — violations fail the stage):
- Acts must partition the chapters: every chapter belongs to exactly one act, none left over.
- The tension curve has exactly one entry per chapter.
- Arc beats reference canon character IDS. Every protagonist and antagonist gets at least one beat.
- Motifs: `payoff_ch` >= `setup_ch`. Promises: `kept_ch` >= `made_ch`, or 0 for a promise you are
  deliberately leaving unresolved.

Meaning rules (checked by a fresh Intent checker):
- Every chapter must do work: carry a beat, a turn, or a ledger event. No connective-tissue chapters.
- The central question must stay open until the ending answers it.
- A beat changes a character's state; it does not restate a fact already in canon.
- Every motif's payoff must land *because* of its setup. Cut decorative motifs.
- Every promise is kept, or pointedly broken — never quietly dropped.
- The shape must be this author's, judged by their obsessions, not by general craft.
- Honour the brief's forbidden list absolutely."""


def _repair_prompt(draft: MacroArcDraft, issues: List[Issue]) -> str:
    return f"""The macro arc you produced failed review.

## Issues to fix
{format_issues(issues)}

## Your current arc
{draft.model_dump_json(indent=2)}

## Task
Emit the CORRECTED full arc.

- Fix exactly what the issues name. Do not re-plan the book or rename anything that was accepted.
- Keep every id stable: a beat, motif or promise that was fine keeps its id.
- If an issue says a chapter does no work, give it work or remove the chapter and renumber
  consistently — do not paper over it with a vaguer purpose."""


async def build_macro_arc(
    *,
    canon: StoryModel,
    brief: Brief,
    author: AuthorModel,
    llm: StructuredLLM,
    tracer: Optional[Tracer] = None,
    intent_checker: Optional[IntentChecker] = None,
    model: str = "sonnet",
    max_repairs: int = 2,
    strict: bool = True,
    max_tokens: int = 20000,
) -> MacroArcResult:
    """Run stage 3. Returns the arc plus the canon with its ledger promoted (uncommitted)."""
    tracer = tracer or Tracer(None)
    base_issues = validate(canon)

    async def evaluate(draft: MacroArcDraft) -> List[Issue]:
        issues = validate_macro_arc_draft(draft, canon)
        issues += _new_issues(base_issues, validate(promote_ledger(canon, draft)))
        if blocking(issues) or intent_checker is None:
            return issues  # cheap gate first: never spend an LLM call on a structurally broken arc
        verdict = await intent_checker.check_macro_arc(
            draft, canon, author_block=author.conception_block()
        )
        if verdict.decision == Decision.ESCALATE:
            raise Escalation("macro_arc", verdict.conflict, verdict)
        return issues + verdict.to_issues("intent")

    outcome = await run_gated(
        llm=llm,
        schema=MacroArcDraft,
        system=SYSTEM,
        prompt=_draft_prompt(canon, brief, author),
        repair_prompt=_repair_prompt,
        evaluate=evaluate,
        stage="macro_arc",
        model=model,
        max_tokens=max_tokens,
        tracer=tracer,
        max_repairs=max_repairs,
        strict=strict,
        failure=MacroArcGateFailed,
    )

    draft: MacroArcDraft = outcome.draft  # type: ignore[assignment]
    return MacroArcResult(
        arc=to_macro_arc(draft),
        canon=promote_ledger(canon, draft),
        issues=outcome.issues,
        repairs=outcome.repairs,
    )
