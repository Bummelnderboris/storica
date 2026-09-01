"""
The ledger pass: advance motif and promise status, but only for what the prose actually delivered.

The plan says what should happen; the extraction says what did. Bumping status from the plan alone
would make the ledger bookkeeping rather than a measure of meaning — the book would report every
promise kept while keeping none.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from ...canon import MotifStatus, PromiseStatus, StoryModel
from ...plan import ChapterSpec
from .schema import ChapterExtraction, Flag, FlagKind, LedgerKind, LedgerObservation, LedgerUpdate

def _update_ledger(
    canon: StoryModel,
    extraction: ChapterExtraction,
    spec: ChapterSpec,
    chapter: int,
    flagged: List[Flag],
) -> List[LedgerUpdate]:
    """
    Advance motif/promise status — but only for assignments the prose actually delivered.

    The plan says what should happen; the extraction says what did. Bumping status from the plan
    alone would make the ledger bookkeeping rather than a measure of meaning: the book would report
    every promise kept while keeping none.
    """
    observations: Dict[Tuple[LedgerKind, str], LedgerObservation] = {
        (o.kind, o.id): o for o in extraction.ledger
    }
    motifs = {m.id: m for m in canon.motifs}
    promises = {p.id: p for p in canon.promises}
    updates: List[LedgerUpdate] = []

    def _landed(kind: LedgerKind, entry_id: str, what: str) -> bool:
        o = observations.get((kind, entry_id))
        if o is not None and o.landed:
            return True
        missing = o.evidence if o is not None else "the extraction did not report on it"
        flagged.append(Flag(
            kind=FlagKind.LEDGER_MISSING,
            ref=entry_id,
            reason=f"chapter {chapter} was assigned to {what} '{entry_id}', but the prose does not "
                   f"deliver it — status not advanced",
            evidence=missing,
        ))
        return False

    def _known(entry_id: str, table: dict, kind: str) -> bool:
        if entry_id in table:
            return True
        flagged.append(Flag(
            kind=FlagKind.LEDGER_UNKNOWN,
            ref=entry_id,
            reason=f"the chapter spec assigns {kind} '{entry_id}', which is not in the canon ledger",
        ))
        return False

    for mid in spec.setups:
        if not _known(mid, motifs, "motif setup") or not _landed(LedgerKind.MOTIF_SETUP, mid, "set up"):
            continue
        m = motifs[mid]
        before = m.status
        if m.setup_ch is None:
            m.setup_ch = chapter
        if m.status == MotifStatus.PLANNED:
            m.status = MotifStatus.SETUP
        if m.status != before:
            updates.append(LedgerUpdate(
                id=mid, kind="motif", chapter=chapter,
                from_status=before.value, to_status=m.status.value,
                note="planted in the prose",
            ))

    for mid in spec.payoffs:
        if not _known(mid, motifs, "motif payoff") or not _landed(LedgerKind.MOTIF_PAYOFF, mid, "pay off"):
            continue
        m = motifs[mid]
        if m.setup_ch is not None and chapter < m.setup_ch:
            flagged.append(Flag(
                kind=FlagKind.LEDGER_ORDER,
                ref=mid,
                reason=f"motif '{mid}' would pay off in ch{chapter} but is set up in ch{m.setup_ch}",
            ))
            continue
        if m.status == MotifStatus.PLANNED:
            flagged.append(Flag(
                kind=FlagKind.LEDGER_ORDER,
                ref=mid,
                reason=f"motif '{mid}' pays off in ch{chapter} but was never recorded as set up",
            ))
        before = m.status
        if m.payoff_ch is None:
            m.payoff_ch = chapter
        m.status = MotifStatus.PAID_OFF
        if m.status != before:
            updates.append(LedgerUpdate(
                id=mid, kind="motif", chapter=chapter,
                from_status=before.value, to_status=m.status.value,
                note="delivered in the prose",
            ))

    for pid in spec.promises_made:
        if not _known(pid, promises, "promise") or not _landed(LedgerKind.PROMISE_MADE, pid, "make promise"):
            continue
        p = promises[pid]
        if p.made_ch is None:
            p.made_ch = chapter
            updates.append(LedgerUpdate(
                id=pid, kind="promise", chapter=chapter,
                from_status=p.status.value, to_status=p.status.value,
                note=f"made_ch set to {chapter}",
            ))

    for pid in spec.promises_kept:
        if not _known(pid, promises, "promise") or not _landed(LedgerKind.PROMISE_KEPT, pid, "keep promise"):
            continue
        p = promises[pid]
        if p.made_ch is not None and chapter < p.made_ch:
            flagged.append(Flag(
                kind=FlagKind.LEDGER_ORDER,
                ref=pid,
                reason=f"promise '{pid}' would be kept in ch{chapter} but is made in ch{p.made_ch}",
            ))
            continue
        before = p.status
        if p.kept_ch is None:
            p.kept_ch = chapter
        if p.status == PromiseStatus.OPEN:
            p.status = PromiseStatus.KEPT
        if p.status != before:
            updates.append(LedgerUpdate(
                id=pid, kind="promise", chapter=chapter,
                from_status=before.value, to_status=p.status.value,
                note="kept on the page",
            ))

    return updates
