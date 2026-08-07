"""
Deterministic structural validation of a StoryModel. No LLM.

This is the fast, certain gate. It catches the *mechanical* failures that sank v1
(see /novels/der-chrachen/FINDINGS.md):
- dangling references (a relationship/timeline points to a non-existent character)
- name fragmentation (the same name resolves to two character ids — the F7/F10 root cause)
- motif/promise ledger inconsistencies (payoff before setup; status vs fields)
- timeline id/order sanity

Semantic contradictions (a priest who behaves like a creditor, a fact that changed meaning)
are the LLM Canon-Consistency checker's job (P5). This module is the deterministic backbone
that runs on every canon write.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List

from .model import CharacterRole, MotifStatus, PromiseStatus, StoryModel


class Severity(str, Enum):
    BLOCKING = "blocking"
    WARNING = "warning"


@dataclass
class Issue:
    code: str
    severity: Severity
    message: str
    ref: str = ""  # id / path the issue concerns

    def __str__(self) -> str:
        loc = f" ({self.ref})" if self.ref else ""
        return f"[{self.severity.value}] {self.code}{loc}: {self.message}"


def _norm(name: str) -> str:
    return " ".join(name.strip().lower().split())


def validate(model: StoryModel) -> List[Issue]:
    """Return every structural issue in `model` (blocking + warning)."""
    issues: List[Issue] = []
    ids = model.character_ids()

    # 1) Referential integrity ---------------------------------------------------------------
    for i, rel in enumerate(model.relationships):
        for side in ("a", "b"):
            cid = getattr(rel, side)
            if cid not in ids:
                issues.append(Issue(
                    "ref.relationship", Severity.BLOCKING,
                    f"relationship[{i}].{side} references unknown character id '{cid}'", cid))
    for ev in model.timeline:
        for cid in ev.involves:
            if cid not in ids:
                issues.append(Issue(
                    "ref.timeline", Severity.BLOCKING,
                    f"timeline '{ev.id}' involves unknown character id '{cid}'", ev.id))

    # 2) Name fragmentation / alias collisions (THE v1 root cause: F7/F10) --------------------
    name_owner: dict[str, str] = {}  # normalized surface name -> character id
    for cid, ch in model.characters.items():
        for nm in ch.all_names():
            key = _norm(nm)
            if not key:
                issues.append(Issue(
                    "canon.empty_name", Severity.WARNING,
                    f"character '{cid}' has an empty name/alias", cid))
                continue
            owner = name_owner.get(key)
            if owner is not None and owner != cid:
                issues.append(Issue(
                    "canon.name_collision", Severity.BLOCKING,
                    f"name '{nm}' maps to two characters ('{owner}' and '{cid}') — "
                    f"name fragmentation, the v1 Rutz/Stettler failure mode", cid))
            else:
                name_owner[key] = cid

    # 3) Timeline sanity ---------------------------------------------------------------------
    seen_ev: set[str] = set()
    for ev in model.timeline:
        if ev.id in seen_ev:
            issues.append(Issue("timeline.dup_id", Severity.BLOCKING,
                                 f"duplicate timeline id '{ev.id}'", ev.id))
        seen_ev.add(ev.id)
    ordered = [ev for ev in model.timeline if ev.order is not None]
    for prev, cur in zip(ordered, ordered[1:]):
        if cur.order < prev.order:  # type: ignore[operator]
            issues.append(Issue(
                "timeline.order", Severity.WARNING,
                f"timeline '{cur.id}' (order {cur.order}) appears after '{prev.id}' "
                f"(order {prev.order}) but sorts earlier", cur.id))

    # 4) Motif ledger ------------------------------------------------------------------------
    seen_m: set[str] = set()
    for m in model.motifs:
        if m.id in seen_m:
            issues.append(Issue("motif.dup_id", Severity.BLOCKING, f"duplicate motif id '{m.id}'", m.id))
        seen_m.add(m.id)
        if m.setup_ch is not None and m.payoff_ch is not None and m.payoff_ch < m.setup_ch:
            issues.append(Issue(
                "motif.payoff_before_setup", Severity.BLOCKING,
                f"motif '{m.id}' pays off (ch{m.payoff_ch}) before it is set up (ch{m.setup_ch})", m.id))
        if m.status == MotifStatus.PAID_OFF and m.payoff_ch is None:
            issues.append(Issue("motif.status", Severity.WARNING,
                                 f"motif '{m.id}' is 'paid_off' but has no payoff_ch", m.id))

    # 5) Promise ledger ----------------------------------------------------------------------
    seen_p: set[str] = set()
    for p in model.promises:
        if p.id in seen_p:
            issues.append(Issue("promise.dup_id", Severity.BLOCKING, f"duplicate promise id '{p.id}'", p.id))
        seen_p.add(p.id)
        if p.made_ch is not None and p.kept_ch is not None and p.kept_ch < p.made_ch:
            issues.append(Issue(
                "promise.kept_before_made", Severity.BLOCKING,
                f"promise '{p.id}' kept (ch{p.kept_ch}) before it is made (ch{p.made_ch})", p.id))
        if p.status == PromiseStatus.KEPT and p.kept_ch is None:
            issues.append(Issue("promise.status", Severity.WARNING,
                                 f"promise '{p.id}' is 'kept' but has no kept_ch", p.id))

    # 6) Cast sanity -------------------------------------------------------------------------
    if model.characters and not any(
        ch.role == CharacterRole.PROTAGONIST for ch in model.characters.values()
    ):
        issues.append(Issue("cast.no_protagonist", Severity.WARNING,
                             "no character has role 'protagonist'"))

    # 7) Constraints -------------------------------------------------------------------------
    if not model.constraints.language.strip():
        issues.append(Issue("constraints.language", Severity.WARNING, "constraints.language is empty"))

    return issues


def blocking(issues: List[Issue]) -> List[Issue]:
    return [i for i in issues if i.severity == Severity.BLOCKING]


def is_valid(model: StoryModel) -> bool:
    """True iff the model has no BLOCKING issues (warnings are allowed)."""
    return not blocking(validate(model))
