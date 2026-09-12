"""
Stage 6's prompts.

The system prompt is the load-bearing one in this stage: it is where the model is told, in as many
words, that the prose is not truth and that merging two contradictory facts into a convenient third
is the single failure this pipeline exists to prevent.
"""

from __future__ import annotations

from typing import List

from ...canon import StoryModel, canon_slice
from ...plan import ChapterSpec
from .schema import LedgerKind

SYSTEM = """You are the Reconcile agent of an autonomous novel pipeline.

You read a finished chapter draft against the canon it was written from, and you report what the
prose actually contains. You do not edit canon, you do not rewrite prose, and you do not decide who
is right when they disagree.

THE PROSE IS NOT TRUTH. CANON IS TRUTH. A draft that calls the priest a creditor does not make him
one — that is a contradiction for you to REPORT, never a correction for you to apply and never two
facts for you to merge into a convenient third one ("he is a priest AND a creditor"). Inventing that
bridging fact is the single failure this pipeline exists to prevent.

You report four things: facts the prose adds that canon does not have, names the prose used for
canon characters, facts the prose contradicts, and whether each setup, payoff and promise this
chapter was assigned actually landed in the text."""


def reconcile_assignment_block(chapter: int, canon: StoryModel, spec: ChapterSpec) -> str:
    """The ledger work this chapter was told to do. The extractor answers landed/not for each line."""
    motifs = {m.id: m for m in canon.motifs}
    promises = {p.id: p for p in canon.promises}

    def _lines(ids: List[str], kind: LedgerKind, table: dict, verb: str) -> List[str]:
        out = []
        for i in ids:
            entry = table.get(i)
            desc = entry.desc if entry is not None else "(NOT IN CANON — report landed=false)"
            out.append(f"- {kind.value} [{i}] — {verb}: {desc}")
        return out

    lines = (
        _lines(spec.setups, LedgerKind.MOTIF_SETUP, motifs, "must be planted on the page")
        + _lines(spec.payoffs, LedgerKind.MOTIF_PAYOFF, motifs, "must be delivered on the page")
        + _lines(spec.promises_made, LedgerKind.PROMISE_MADE, promises, "must be made to the reader")
        + _lines(spec.promises_kept, LedgerKind.PROMISE_KEPT, promises, "must be kept on the page")
    )
    body = "\n".join(lines) or "- (this chapter was assigned no ledger work)"

    return f"""# Ledger assignments for chapter {chapter}
Report exactly one observation per line below, with `landed` true or false. An assignment the plan
made but the prose did not deliver is a finding — say so. Do not report it as landed to be helpful.

{body}"""


def _extraction_prompt(chapter: int, draft_text: str, canon: StoryModel, spec: ChapterSpec) -> str:
    cids = list(dict.fromkeys([spec.pov_character_id, *spec.present_character_ids]))
    motif_ids = list(dict.fromkeys([*spec.setups, *spec.payoffs]))
    promise_ids = list(dict.fromkeys([*spec.promises_made, *spec.promises_kept]))

    return f"""{canon_slice(canon, character_ids=cids, motif_ids=motif_ids, promise_ids=promise_ids)}

# Ids under review in chapter {chapter}
- characters: {', '.join(cids) or '(none)'}
- motifs: {', '.join(motif_ids) or '(none)'}
- promises: {', '.join(promise_ids) or '(none)'}

{reconcile_assignment_block(chapter, canon, spec)}

# Chapter {chapter} draft
{draft_text}

## Task
Reconcile the draft above against the canon slice above.

Rules:
- Report facts the draft ESTABLISHES, not what it implies and not what you know from elsewhere.
  If it is not on the page, it does not exist.
- Every fact and alias is attached to a character ID from the list under review. If the draft names
  someone canon does not have, do not invent an id — report it as a contradiction against the
  character you believe was meant.
- `surface_name` is the name the prose used, verbatim. Never replace it with the canonical name:
  the difference between them is exactly what we are looking for.
- Anything the draft says that the slice says otherwise about goes in `contradictions` — including
  a role, a relationship, a date, or a cause of death. Do NOT resolve it. Do NOT choose a winner.
  Do NOT invent a fact under which both could be true. Canon is ground truth; the draft is a draft.
- A fact the slice already states is NOT a contradiction. Do NOT report it again, and do NOT
  report it reworded: a restatement in different words is indistinguishable from a changed fact
  and would be flagged as a contradiction. Report only what is new or what disagrees.
- For the ledger: `landed` is about the page, not the plan. If the chapter was told to pay a motif
  off and the payoff is not in the text, say landed=false and name what is missing."""
