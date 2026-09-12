"""
The Final Auditor — the last gate before a novel is declared done (DESIGN §6.5, P6).

Every other checker reads one unit. Each of them can pass everything it sees and still leave a book
where a fact quietly changed between chapter 2 and chapter 9, where a character behaves as two
people, or where a promise made in the first act is simply never mentioned again — because no unit
is wrong on its own. Only the whole book shows that, and this is the only agent that reads it.

It is a fresh reader in the strongest sense the pipeline has: it gets the assembled novel, the full
canon, the arc, and the ledger, and *no* memory of how any of it was produced — no verdicts, no
repair history, no knowledge of which chapters were hard. If the book only works for someone who
watched it being made, it does not work.

Two disciplines keep it from becoming a rewriter:

- **It proposes no canon edits and invents no bridging facts.** On a canon-side incoherence it
  returns `ESCALATE` and describes the conflict; the caller adjudicates (§6.5). An auditor that
  "reconciles" a contradiction at the end of the run would be F11/F12 with nothing downstream left
  to catch it.
- **The cheap check runs first.** `audit_ledger` mechanically walks the promise/motif ledger before
  the model is called, and its findings go into the prompt. The auditor then reads the book with
  the open promises already in hand, instead of spending its attention rediscovering bookkeeping it
  cannot do reliably across a hundred thousand words.
"""

from __future__ import annotations

from typing import List, Sequence

from ..llm import stage_model
from ..canon import Issue, MotifStatus, PromiseStatus, Severity, StoryModel, canon_slice
from ..plan import MacroArc
from .base import Checker, Verdict

SYSTEM = """You are the Final Auditor of an autonomous novel pipeline.

You are reading a finished book. You did not write any of it and you have
no memory of how it was produced — no drafts, no earlier verdicts, no knowledge of which parts were
difficult. You are the reader the book will actually meet. Judge only what is on the page, against
the canon given.

You do NOT rewrite and you do NOT score. A number would let a book that abandons its own question
pass because the sentences are good. Return a verdict with a list of issues:
- 'pass'     — the book coheres, keeps what it promised, and its ending answers its central question.
- 'revise'   — fixable; every issue names the chapter at fault and the smallest change that fixes it.
- 'escalate' — the canon itself is incoherent, or the book cannot be made to work without changing
               something upstream. Describe it in `conflict`.

You may NOT propose a change to canon, and you may NOT invent a fact that would make two
irreconcilable things fit. If the canon is what looks wrong, escalate — someone else rules on it.

This is the last gate. Nothing checks the book after you."""

AUDIT_RUBRIC = """Read the whole book, then answer four questions in this order.

1. **Does it cohere across its whole length?** This is the only reading that can see it. Look for:
   a fact stated one way early and another way late (a name, an age, a profession, a distance, who
   owns what, who knows what); a character who behaves as two different people in two different
   chapters without the book making that a change; a timeline that cannot have happened — someone
   in two places, an event referred to before it occurs, a season or duration that does not add up.
   Cite both chapters in `unit`, e.g. `ch02 vs ch09`. Contradiction is BLOCKING.

2. **Is every promise kept?** Walk the ledger above, one entry at a time, and find where in the text
   it lands. A promise the book *deliberately* leaves unkept is legitimate — but only if the book
   makes the refusal on the page, so the reader knows it was refused rather than forgotten. A
   promise that is silently dropped is BLOCKING. Same for motifs: a motif planted and never paid
   off is BLOCKING; a motif dropped deliberately and visibly is not. Where the ledger findings below
   say a promise is open, confirm against the text — either it is genuinely unkept (blocking), or
   the ledger is stale because the text keeps it (a warning about the record, not the book).

3. **Are any units missing?** A quarantined unit means the book is not done, no matter how well the
   remaining chapters read. Report each one, and report what its absence does to the chapters
   around it.

4. **Does the ending answer the central question?** The central question is the contract with the
   reader; the ending is where it is honoured or broken. An answer may be bleak, partial, or an
   answer the reader did not want — a Dürrenmatt ending that refuses consolation has answered. What
   fails is an ending that changes the subject, or that resolves something the book never asked.
   Ending on a different question than the book opened is BLOCKING.

How to report:
- `unit`: the chapter(s) at fault, e.g. `ch07`, or `ch02 vs ch09` for a contradiction across two.
- `canon_ref`: the canon id it is grounded in — character id, world_fact key, timeline id, motif id,
  promise id — or empty when canon says nothing about it.
- `fix_hint`: the smallest change. Naming the chapter to cut or the sentence to correct is a fix;
  "tighten the middle" is not.
- Not an issue: a book you would have written differently. You are not the author."""


def audit_ledger(canon: StoryModel) -> List[Issue]:
    """
    The meaning ledger, checked mechanically. No LLM.

    Whether a promise *reads* as kept is a judgement; whether the ledger claims it was is not, and
    a model asked to track fifty ids across a whole novel will miss some. This runs first so the
    auditor reads with the bookkeeping already done.
    """
    issues: List[Issue] = []

    for p in canon.promises:
        if p.status == PromiseStatus.OPEN and p.kept_ch is None:
            # The arc scheduled no chapter to keep it in (`kept_ch: 0` at planning time), so it
            # was never meant to be resolved. Nothing in the pipeline marks a promise BROKEN on
            # its own; this is where "deliberately unresolved" is recognised, and it is a
            # judgement for the auditor, not a mechanical failure.
            issues.append(Issue(
                "audit.promise_unresolved", Severity.WARNING,
                f"promise '{p.id}' was planned as deliberately unresolved (made ch{p.made_ch}): "
                f"{p.desc} — confirm the book withholds it on purpose and the reader can feel that",
                p.id,
            ))
        elif p.status == PromiseStatus.OPEN:
            issues.append(Issue(
                "audit.promise_open", Severity.BLOCKING,
                f"promise '{p.id}' is still open at the end of the book (made ch{p.made_ch}, "
                f"due ch{p.kept_ch}): {p.desc}",
                p.id,
            ))
        elif p.status == PromiseStatus.BROKEN:
            issues.append(Issue(
                "audit.promise_broken", Severity.WARNING,
                f"promise '{p.id}' is marked broken: {p.desc} — legitimate only if the book breaks "
                f"it on the page; confirm the refusal is visible to the reader",
                p.id,
            ))
        elif p.status == PromiseStatus.KEPT and p.kept_ch is None:
            issues.append(Issue(
                "audit.promise_kept_nowhere", Severity.WARNING,
                f"promise '{p.id}' is marked kept but records no chapter that keeps it", p.id,
            ))
        if p.made_ch is not None and p.kept_ch is not None and p.kept_ch < p.made_ch:
            issues.append(Issue(
                "audit.promise_order", Severity.BLOCKING,
                f"promise '{p.id}' is kept in ch{p.kept_ch}, before it is made in ch{p.made_ch}", p.id,
            ))

    for m in canon.motifs:
        if m.status == MotifStatus.PLANNED:
            issues.append(Issue(
                "audit.motif_unplaced", Severity.BLOCKING,
                f"motif '{m.id}' was scheduled (setup ch{m.setup_ch}, payoff ch{m.payoff_ch}) but is "
                f"still only planned — it never entered the book: {m.desc}",
                m.id,
            ))
        elif m.status == MotifStatus.SETUP:
            issues.append(Issue(
                "audit.motif_unpaid", Severity.BLOCKING,
                f"motif '{m.id}' was planted (ch{m.setup_ch}) and never paid off (due ch{m.payoff_ch}): "
                f"{m.desc}",
                m.id,
            ))
        elif m.status == MotifStatus.DROPPED:
            issues.append(Issue(
                "audit.motif_dropped", Severity.WARNING,
                f"motif '{m.id}' was dropped: {m.desc} — confirm nothing in the text still leans on it",
                m.id,
            ))
        if m.setup_ch is not None and m.payoff_ch is not None and m.payoff_ch < m.setup_ch:
            issues.append(Issue(
                "audit.motif_order", Severity.BLOCKING,
                f"motif '{m.id}' pays off in ch{m.payoff_ch}, before it is set up in ch{m.setup_ch}", m.id,
            ))

    return issues


def _ledger_findings_block(findings: Sequence[Issue]) -> str:
    if not findings:
        return (
            "# Ledger findings (mechanical pre-check)\n"
            "The ledger is clean: every promise is recorded as kept or deliberately broken, and every "
            "motif as paid off or deliberately dropped. Verify that the text agrees with the record."
        )
    lines = "\n".join(f"- {i}" for i in findings)
    return f"""# Ledger findings (mechanical pre-check — established, do not re-derive)
These come from the ledger itself, not from a reading. Confirm each one against the text: either the
book really does leave it unresolved, or the record is stale.
{lines}"""


def _quarantine_block(quarantined: Sequence[str]) -> str:
    if not quarantined:
        return "# Quarantined units\n(none — every planned unit is present in the text below)"
    units = "\n".join(f"- {u}" for u in quarantined)
    return f"""# Quarantined units — THE BOOK IS NOT DONE
These units could not be made correct within their repair budget and were excluded from the text
below, leaving holes in it. This is blocking on its own, whatever else you find:
{units}"""


def _arc_block(arc: MacroArc) -> str:
    acts = "\n".join(
        f"- act {a.number} — {a.title} (ch {', '.join(str(c) for c in a.chapters)}): {a.purpose}"
        for a in arc.acts
    ) or "- (no acts recorded)"
    turns = "\n".join(
        f"- [{t.id}] ch{t.chapter}: {t.description} (reverses: {t.reverses})" for t in arc.turning_points
    ) or "- (none recorded)"
    return f"""# The shape the book was built to have
- chapters planned: {arc.chapter_count}
- shape: {arc.shape}
- acts:
{acts}
- turning points:
{turns}"""


class FinalAuditor(Checker):
    """Whole-book fresh reader: coherence, promises kept, nothing quarantined, the question answered."""

    name = "final_auditor"

    SYSTEM = SYSTEM
    DEFAULT_MODEL = stage_model("final_auditor")
    DEFAULT_MAX_TOKENS = 16000
    TRACE_STAGE = "final_audit"

    async def audit(
        self,
        *,
        novel_text: str,
        canon: StoryModel,
        arc: MacroArc,
        quarantined: Sequence[str] = (),
    ) -> Verdict:
        """Read the finished book once, with the whole canon and the ledger pre-check in hand."""
        findings = audit_ledger(canon)

        prompt = f"""{canon_slice(canon)}

{_arc_block(arc)}

# The contract with the reader
The central question this book exists to answer:
    {canon.premise.central_question or '(none recorded — say so, it is a finding)'}

{_ledger_findings_block(findings)}

{_quarantine_block(quarantined)}

# The finished book, as a reader receives it
{novel_text}

{AUDIT_RUBRIC}"""
        return await self.check(prompt=prompt, unit="novel")
