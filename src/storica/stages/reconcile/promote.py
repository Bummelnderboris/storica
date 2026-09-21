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

from ...canon import Awareness, Knowing, StoryModel, TimelineEvent, norm, slug
from ...canon.slice import _due_chapter
from .schema import ChapterExtraction, FactRelation, Flag, FlagKind, Promotion, PromotionKind


def _classify(current: Optional[str], value: str, relation: FactRelation) -> str:
    """
    'promote' | 'ignore' | 'restated' | 'contradiction' for one extracted fact against canon.

    The extractor's judgement decides the paraphrase question (only a reader can tell a restatement
    from a change); code keeps the conservative backstop — an extractor that calls a fact new while
    canon already fills that key with something else has found a contradiction, whatever it says.
    """
    if relation is FactRelation.CONTRADICTS:
        return "contradiction"
    if current is None:
        return "promote" if relation is FactRelation.NEW else "ignore"
    if norm(current) == norm(value):
        return "ignore"
    return "restated" if relation is FactRelation.RESTATES else "contradiction"

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
            verdict = _classify(current, f.value, f.relation_to_canon)
            if verdict == "promote":
                canon.characters[cid].facts[key] = f.value.strip()
                promoted.append(Promotion(
                    kind=PromotionKind.CHARACTER_FACT,
                    ref=f"{cid}.{key}",
                    value=f.value.strip(),
                    evidence=f.evidence,
                ))
            elif verdict == "restated":
                flagged.append(Flag(
                    kind=FlagKind.RESTATED,
                    ref=f"{cid}.{key}",
                    reason=f"the draft restates '{key}' for '{cid}' in other words — canon's wording stands",
                    canon_says=current or "",
                    prose_says=f.value.strip(),
                    evidence=f.evidence,
                ))
            elif verdict == "contradiction":
                # Canon wins by construction. We record the disagreement and change nothing.
                flagged.append(Flag(
                    kind=FlagKind.CONTRADICTION,
                    ref=f"{cid}.{key}",
                    reason=f"the draft states a different '{key}' for '{cid}' than canon does",
                    canon_says=current or "",
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
        verdict = _classify(current, w.value, w.relation_to_canon)
        if verdict == "promote":
            canon.world_facts[key] = w.value.strip()
            promoted.append(Promotion(
                kind=PromotionKind.WORLD_FACT, ref=f"world:{key}", value=w.value.strip(), evidence=w.evidence
            ))
        elif verdict == "restated":
            flagged.append(Flag(
                kind=FlagKind.RESTATED,
                ref=f"world:{key}",
                reason=f"the draft restates '{key}' in other words — canon's wording stands",
                canon_says=current or "",
                prose_says=w.value.strip(),
                evidence=w.evidence,
            ))
        elif verdict == "contradiction":
            flagged.append(Flag(
                kind=FlagKind.CONTRADICTION,
                ref=f"world:{key}",
                reason=f"the draft states a different '{key}' than canon does",
                canon_says=current or "",
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
    Place events in story order, deduplicated by text and by id.

    v1 `list.append()`ed timeline entries with no dedup at all, so the same event accumulated once
    per chapter and inflated every prompt downstream (F7). An event we cannot fully resolve is
    dropped and flagged rather than promoted with a dangling reference — a broken canon is worse
    than a missing entry.

    An event lands where the extractor says it belongs in *story* time (`after_event_id`), not at
    the end: a chapter that reveals something from twenty years ago must not leave it sorted after
    last night (DESIGN §10 risk 6). An unknown anchor falls back to the end, which is where the
    chapter's own present goes anyway.
    """
    known_events = {norm(ev.event): ev.id for ev in canon.timeline}

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

        known_events[norm(t.event)] = tid
        _place(canon, TimelineEvent(
            id=tid,
            when=t.when.strip() or f"ch{chapter}",
            event=t.event.strip(),
            involves=[r for _, r in refs if r is not None],
        ), after=slug(t.after_event_id) if t.after_event_id.strip() else "")
        promoted.append(Promotion(
            kind=PromotionKind.TIMELINE, ref=tid, value=t.event.strip(), evidence=t.evidence
        ))


def _place(canon: StoryModel, event: TimelineEvent, *, after: str) -> None:
    """Insert `event` after the event `after` in story order, then renumber `order` to match."""
    ordered = sorted(
        canon.timeline, key=lambda e: (e.order is None, e.order if e.order is not None else 0)
    )
    anchor = next((i for i, e in enumerate(ordered) if e.id == after), None) if after else None
    ordered.insert(len(ordered) if anchor is None else anchor + 1, event)
    for n, e in enumerate(ordered, start=1):
        e.order = n
    canon.timeline[:] = ordered


_RANK = {
    Awareness.UNAWARE: 0,
    Awareness.BELIEVES_FALSE: 1,
    Awareness.SUSPECTS: 1,
    Awareness.KNOWS: 2,
}


def _promote_knowledge(
    canon: StoryModel,
    extraction: ChapterExtraction,
    chapter: int,
    promoted: List[Promotion],
    flagged: List[Flag],
) -> None:
    """
    Carry who-knows-what forward from the page (DESIGN §10 risk 7).

    Stage 2 wrote the knowledge table once, and nothing after it could change: a character who
    learned the secret in chapter 2 was still `unaware` in every slice written for chapter 3. Now a
    shift the prose delivers is recorded with `since: chN`.

    Knowledge only moves forward. A character who knew something cannot un-know it, so a shift that
    lowers awareness is a contradiction for adjudication, not an update. A shift the plan scheduled
    for a *later* chapter arriving early is also flagged: the chapter took a later chapter's turn.
    """
    items = {k.id: k for k in canon.knowledge}
    for s in extraction.knowledge_shifts:
        item = items.get(s.knowledge_id.strip())
        cid = _resolve_character(canon, s.character_id)
        if item is None or cid is None:
            flagged.append(Flag(
                kind=FlagKind.UNRESOLVED_REFERENCE,
                ref=s.knowledge_id or s.character_id,
                reason=f"knowledge shift for '{s.character_id}' on '{s.knowledge_id}' names an id "
                       f"canon does not have — not promoted",
                prose_says=s.awareness.value,
                evidence=s.evidence,
            ))
            continue

        holder = next((h for h in item.holders if h.character_id == cid), None)
        due = _due_chapter(holder.since) if holder is not None else None
        # What they hold as this chapter stands: a shift scheduled for a later chapter has not
        # happened yet, so until then they are unaware (the slice renders it the same way).
        before = (
            Awareness.UNAWARE if holder is None or (due is not None and due > chapter)
            else holder.awareness
        )
        if s.awareness == before:
            continue                                   # consistent — canon already has it

        if due is not None and due > chapter:
            flagged.append(Flag(
                kind=FlagKind.CONTRADICTION,
                ref=f"knowledge:{item.id}:{cid}",
                reason=f"'{cid}' becomes '{s.awareness.value}' on '{item.id}' in ch{chapter}, but the "
                       f"plan schedules that shift for ch{due}",
                canon_says=f"unaware until ch{due}",
                prose_says=f"{s.awareness.value} in ch{chapter}",
                evidence=s.evidence,
            ))
            continue
        if _RANK[s.awareness] < _RANK[before]:
            flagged.append(Flag(
                kind=FlagKind.CONTRADICTION,
                ref=f"knowledge:{item.id}:{cid}",
                reason=f"the draft lowers '{cid}' from '{before.value}' to '{s.awareness.value}' on "
                       f"'{item.id}' — knowledge does not run backwards",
                canon_says=before.value,
                prose_says=s.awareness.value,
                evidence=s.evidence,
            ))
            continue

        if holder is None:
            holder = Knowing(character_id=cid)
            item.holders.append(holder)
        holder.awareness = s.awareness
        holder.since = f"ch{chapter}"
        holder.instead = s.instead.strip() if s.awareness == Awareness.BELIEVES_FALSE else ""
        promoted.append(Promotion(
            kind=PromotionKind.KNOWLEDGE,
            ref=f"knowledge:{item.id}:{cid}",
            value=f"{before.value} -> {s.awareness.value}",
            evidence=s.evidence,
        ))
