"""
Canon slices — the grounding payload every downstream agent is handed.

Principle 3: *ground every generation in the full relevant canon.* A slice is the complete
canonical truth about the entities a unit touches — every character in scene with all their facts,
aliases and arc, the relationships among them, the timeline they appear in, and the motif/promise
ledger entries assigned to the unit. This is what replaces v1's truncated `raw_blueprint[:800]`
(F5): units get *all* of what they touch, not a prefix of a summary.

Rendered as text, not JSON, because it is prompt material — but every value in it comes straight
from `StoryModel`, so nothing is re-interpreted on the way.
"""

from __future__ import annotations

from typing import Iterable, List, Optional

from .model import StoryModel


def _fmt_facts(facts: dict, indent: str = "    ") -> str:
    return "\n".join(f"{indent}- {k}: {v}" for k, v in facts.items()) or f"{indent}- (none recorded)"


def canon_slice(
    model: StoryModel,
    *,
    character_ids: Optional[Iterable[str]] = None,
    motif_ids: Optional[Iterable[str]] = None,
    promise_ids: Optional[Iterable[str]] = None,
    include_timeline: bool = True,
    include_premise: bool = True,
) -> str:
    """
    Render the canon slice for the given ids. `None` means *everything* of that kind.

    Unknown ids are reported inline rather than skipped — an agent must never silently receive a
    slice that is missing something it was told to use.
    """
    cids: List[str] = list(character_ids) if character_ids is not None else list(model.characters)
    known = [c for c in cids if c in model.characters]
    unknown = [c for c in cids if c not in model.characters]
    in_slice = set(known)

    parts: List[str] = ["# Canon slice (SOURCE OF TRUTH — do not contradict any line below)"]

    if include_premise:
        p = model.premise
        parts.append(
            f"""
## Premise
- spark: {p.spark}
- central_question: {p.central_question}
- thesis: {p.thesis}
- why_this_author: {p.why_this_author}"""
        )

    parts.append("\n## Characters")
    for cid in known:
        ch = model.characters[cid]
        aliases = ", ".join(ch.aliases) if ch.aliases else "(none)"
        block = [
            f"\n### {cid}  ({ch.role.value})",
            f"  canonical_name: {ch.canonical_name}",
            f"  also called: {aliases}",
            "  facts:",
            _fmt_facts(ch.facts),
        ]
        if ch.arc:
            block += [
                "  arc:",
                f"    - want: {ch.arc.want}",
                f"    - need: {ch.arc.need}",
                f"    - flaw: {ch.arc.flaw}",
                f"    - trajectory: {ch.arc.trajectory}",
            ]
        parts.append("\n".join(block))
    for cid in unknown:
        parts.append(f"\n### {cid}\n  !! NOT IN CANON — this id does not exist.")

    rels = [r for r in model.relationships if r.a in in_slice or r.b in in_slice]
    if rels:
        parts.append("\n## Relationships")
        parts.extend(f"- {r.a} is {r.type} {r.b}" for r in rels)

    if model.world_facts:
        parts.append("\n## World facts")
        parts.extend(f"- {k}: {v}" for k, v in model.world_facts.items())

    if include_timeline:
        events = [ev for ev in model.timeline if not in_slice or set(ev.involves) & in_slice or not ev.involves]
        if events:
            parts.append("\n## Timeline")
            parts.extend(
                f"- [{ev.id}] {ev.when}: {ev.event}"
                + (f" (involves: {', '.join(ev.involves)})" if ev.involves else "")
                for ev in sorted(events, key=lambda e: (e.order is None, e.order or 0))
            )

    motifs = model.motifs if motif_ids is None else [m for m in model.motifs if m.id in set(motif_ids)]
    if motifs:
        parts.append("\n## Motifs (ledger)")
        parts.extend(
            f"- [{m.id}] {m.desc} — setup ch{m.setup_ch}, payoff ch{m.payoff_ch}, status: {m.status.value}"
            for m in motifs
        )

    promises = model.promises if promise_ids is None else [p for p in model.promises if p.id in set(promise_ids)]
    if promises:
        parts.append("\n## Promises (ledger)")
        parts.extend(
            f"- [{p.id}] {p.desc} — made ch{p.made_ch}, kept ch{p.kept_ch}, status: {p.status.value}"
            for p in promises
        )

    c = model.constraints
    parts.append(
        f"\n## Constraints\n- language: {c.language}\n- chapter_count: {c.chapter_count}\n"
        + ("- forbidden:\n" + "\n".join(f"    - {f}" for f in c.forbidden) if c.forbidden else "- forbidden: (none)")
    )

    return "\n".join(parts)
