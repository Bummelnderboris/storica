"""
The promotion passes: every extracted item lands in exactly one of three buckets.

  * **new**           — canon has nothing on this key   → promote
  * **consistent**    — canon already says this         → ignore, no duplicate and no rewrite
  * **contradiction** — canon says otherwise            → flag, and canon stands

Nothing in this module overwrites canon. That is the whole inversion (DESIGN §5): a draft that calls
the priest a creditor does not make him one, and the correct terminal behaviour for a disagreement
is a flag that gets adjudicated against ground truth — never a merge, and never letting the draft
win because it was written more recently.
"""

from __future__ import annotations

from typing import List, Optional

from ...canon import StoryModel, TimelineEvent, norm, slug
from .schema import ChapterExtraction, Flag, FlagKind, Promotion, PromotionKind

def _resolve_character(canon: StoryModel, ref: str, surface_name: str = "") -> Optional[str]:
    """
    Map whatever the extractor called a character onto a canon id, or None.

    None is a real answer, not a fallback: an unresolvable reference is flagged rather than guessed
    at, because guessing is how a second "Rutz" gets born.
    """
    ref = ref.strip()
    if ref in canon.characters:
        return ref
    hit = canon.resolve_name(ref) if ref else None
    if hit:
        return hit
    if ref and slug(ref) in canon.characters:
        return slug(ref)
    return canon.resolve_name(surface_name) if surface_name.strip() else None


def _promote_aliases(
    canon: StoryModel, extraction: ChapterExtraction, promoted: List[Promotion], flagged: List[Flag]
) -> None:
    """
    Add surface forms the prose used — unless another character already owns the name.

    The collision check is the F7/F10 fix in one line: v1 keyed characters by name string, so
    "Rutz" could quietly become a second person. Here a name that resolves to somebody else is
    flagged and dropped, never attached. The check runs against the *working* canon, so two aliases
    colliding with each other inside one extraction are caught too.
    """
    for a in extraction.aliases:
        alias = " ".join(a.alias.strip().split())
        if not alias:
            continue
        cid = _resolve_character(canon, a.character_id)
        if cid is None:
            flagged.append(Flag(
                kind=FlagKind.UNKNOWN_CHARACTER,
                ref=a.character_id,
                reason=f"alias '{alias}' was attributed to '{a.character_id}', which is not a canon character",
                prose_says=alias,
                evidence=a.evidence,
            ))
            continue

        owner = canon.resolve_name(alias)
        if owner == cid:
            continue                                   # consistent — canon already knows this name
        if owner is not None:
            flagged.append(Flag(
                kind=FlagKind.ALIAS_COLLISION,
                ref=cid,
                reason=f"'{alias}' is already a name of '{owner}' — attaching it to '{cid}' would "
                       f"fragment the cast, the v1 Rutz failure",
                canon_says=f"{alias} = {owner}",
                prose_says=f"{alias} = {cid}",
                evidence=a.evidence,
            ))
            continue

        canon.characters[cid].aliases.append(alias)
        promoted.append(Promotion(
            kind=PromotionKind.ALIAS, ref=f"alias:{cid}", value=alias, evidence=a.evidence
        ))


def _promote_character_facts(
    canon: StoryModel, extraction: ChapterExtraction, promoted: List[Promotion], flagged: List[Flag]
) -> None:
    for f in extraction.character_facts:
        cid = _resolve_character(canon, f.character_id, f.surface_name)
        if cid is None:
            flagged.append(Flag(
                kind=FlagKind.UNKNOWN_CHARACTER,
                ref=f.character_id,
                reason=f"fact '{f.key}' was attributed to '{f.character_id}', which is not a canon character",
                prose_says=f.value,
                evidence=f.evidence,
            ))
            continue

        key = slug(f.key)
        if key and f.value.strip():
            current = canon.characters[cid].facts.get(key)
            if current is None:
                canon.characters[cid].facts[key] = f.value.strip()
                promoted.append(Promotion(
                    kind=PromotionKind.CHARACTER_FACT,
                    ref=f"{cid}.{key}",
                    value=f.value.strip(),
                    evidence=f.evidence,
                ))
            elif norm(current) != norm(f.value):
                # Canon wins by construction. We record the disagreement and change nothing.
                flagged.append(Flag(
                    kind=FlagKind.CONTRADICTION,
                    ref=f"{cid}.{key}",
                    reason=f"the draft states a different '{key}' for '{cid}' than canon does",
                    canon_says=current,
                    prose_says=f.value.strip(),
                    evidence=f.evidence,
                ))

        _flag_name_drift(canon, cid, f.surface_name, f.evidence, flagged)


def _flag_name_drift(
    canon: StoryModel, cid: str, surface_name: str, evidence: str, flagged: List[Flag]
) -> None:
    """The surface form is the early-warning signal: v1 lost the priest one name variant at a time."""
    surface = " ".join(surface_name.strip().split())
    if not surface:
        return
    owner = canon.resolve_name(surface)
    if owner == cid:
        return
    if owner is None:
        flagged.append(Flag(
            kind=FlagKind.NAME_DRIFT,
            ref=cid,
            reason=f"the draft called '{cid}' \"{surface}\", a name canon does not know — either an "
                   f"unlisted alias or the wrong character",
            prose_says=surface,
            evidence=evidence,
        ))
    else:
        flagged.append(Flag(
            kind=FlagKind.ALIAS_COLLISION,
            ref=cid,
            reason=f"the draft called '{cid}' \"{surface}\", which is '{owner}'s name",
            canon_says=f"{surface} = {owner}",
            prose_says=f"{surface} = {cid}",
            evidence=evidence,
        ))


def _promote_world_facts(
    canon: StoryModel, extraction: ChapterExtraction, promoted: List[Promotion], flagged: List[Flag]
) -> None:
    for w in extraction.world_facts:
        key = slug(w.key)
        if not key or not w.value.strip():
            continue
        current = canon.world_facts.get(key)
        if current is None:
            canon.world_facts[key] = w.value.strip()
            promoted.append(Promotion(
                kind=PromotionKind.WORLD_FACT, ref=f"world:{key}", value=w.value.strip(), evidence=w.evidence
            ))
        elif norm(current) != norm(w.value):
            flagged.append(Flag(
                kind=FlagKind.CONTRADICTION,
                ref=f"world:{key}",
                reason=f"the draft states a different '{key}' than canon does",
                canon_says=current,
                prose_says=w.value.strip(),
                evidence=w.evidence,
            ))


def _promote_timeline(
    canon: StoryModel,
    extraction: ChapterExtraction,
    chapter: int,
    promoted: List[Promotion],
    flagged: List[Flag],
) -> None:
    """
    Append events, deduplicated by text and by id.

    v1 `list.append()`ed timeline entries with no dedup at all, so the same event accumulated once
    per chapter and inflated every prompt downstream (F7). An event we cannot fully resolve is
    dropped and flagged rather than promoted with a dangling reference — a broken canon is worse
    than a missing entry.
    """
    known_events = {norm(ev.event): ev.id for ev in canon.timeline}
    next_order = max((ev.order or 0 for ev in canon.timeline), default=0)

    for i, t in enumerate(extraction.timeline):
        if not t.event.strip():
            continue
        if norm(t.event) in known_events:
            continue                                   # consistent — already on the timeline

        tid = slug(t.id) or f"ch{chapter:02d}_e{i + 1}"
        if any(ev.id == tid for ev in canon.timeline):
            flagged.append(Flag(
                kind=FlagKind.CONTRADICTION,
                ref=tid,
                reason=f"timeline id '{tid}' already exists with a different event",
                canon_says=next(ev.event for ev in canon.timeline if ev.id == tid),
                prose_says=t.event.strip(),
                evidence=t.evidence,
            ))
            continue

        refs = [(x, _resolve_character(canon, x)) for x in t.involves]
        unresolved = [x for x, r in refs if r is None]
        if unresolved:
            flagged.append(Flag(
                kind=FlagKind.UNRESOLVED_REFERENCE,
                ref=tid,
                reason=f"timeline event '{tid}' involves unknown character ids {unresolved} — not promoted",
                prose_says=t.event.strip(),
                evidence=t.evidence,
            ))
            continue

        next_order += 1
        known_events[norm(t.event)] = tid
        canon.timeline.append(TimelineEvent(
            id=tid,
            when=t.when.strip() or f"ch{chapter}",
            event=t.event.strip(),
            involves=[r for _, r in refs if r is not None],
            order=next_order,
        ))
        promoted.append(Promotion(
            kind=PromotionKind.TIMELINE, ref=tid, value=t.event.strip(), evidence=t.evidence
        ))
