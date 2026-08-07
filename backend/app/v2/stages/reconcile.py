"""
Stage 6 — Reconcile a finished chapter draft back into canon (DESIGN §5, §8).

Reads: the draft prose + canon + the chapter spec.  Writes: canon (returned, not committed).

This is the stage that killed v1. The old `phase7_consistency` guardian was a one-way ratchet: it
read the prose and *added whatever the prose said* to the story bible. So when the Writer recast the
priest as a creditor (F9), the guardian wrote "Rutz: local creditor" into canon (F10), the next
chapter's reasoner found bible-vs-plan disagreement and invented a bridging fact to smooth it over
(F11), and the reviser then "fixed" the chapter into a far more broken one (F12). One misreading
became permanent, self-propagating truth.

The inversion here is the whole point (principle 1 and 5):

    prose is never truth — facts are EXTRACTED from prose and VALIDATED INTO canon

so every extracted item lands in exactly one of three buckets:

  * **new** — canon has nothing on this key   → promote
  * **consistent** — canon already says this  → ignore (no duplicate, no rewrite)
  * **contradiction** — canon says otherwise  → **flag**, never overwrite

Flagging is the correct terminal behaviour, not a failure: canon and the brief are ground truth, so
a contradiction is adjudicated (DESIGN §6.5, P5) against ground truth — it is never resolved by
letting the draft win, and never by blending both into a new combined fact.

Extraction is **one** structured call (the v1 double extract call is F3 and is deleted), grounded in
the canon slice for exactly what the chapter touches. The same call reports whether each assigned
setup / payoff / promise actually landed in the text, which is what makes the ledger mean something:
a motif the plan says is `paid_off` but that never appeared is a flagged issue, not a status bump.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from ..canon import (
    Issue,
    MotifStatus,
    PromiseStatus,
    Severity,
    StoryModel,
    TimelineEvent,
    blocking,
    canon_slice,
    validate,
)
from ..llm import StructuredLLM
from ..plan import ChapterSpec
from ..trace import Tracer
from .gate import GateFailed

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


# --------------------------------------------------------------------------------------------
# LLM-facing extraction schema.
# Flat, every field required, no dicts: structured outputs reject anything else.
# --------------------------------------------------------------------------------------------

class LedgerKind(str, Enum):
    MOTIF_SETUP = "motif_setup"
    MOTIF_PAYOFF = "motif_payoff"
    PROMISE_MADE = "promise_made"
    PROMISE_KEPT = "promise_kept"


class CharacterFactExtract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    character_id: str = Field(description="The canon character id this fact is about. An id from the slice, never a name.")
    surface_name: str = Field(
        description="The name the PROSE used for this character in the passage the fact comes from — "
        "verbatim. This is how name drift becomes visible; do not normalise it to the canonical name."
    )
    key: str = Field(description="Short snake_case fact key, e.g. 'profession', 'secret', 'injury'.")
    value: str = Field(description="The fact as the prose states it, flatly. No hedging, no prose flourish.")
    evidence: str = Field(description="The short phrase from the draft that carries it.")


class AliasExtract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    character_id: str = Field(description="The canon character id the name belongs to.")
    alias: str = Field(description="A surface form the draft used for that character, verbatim.")
    evidence: str = Field(description="The short phrase from the draft where it is used.")


class WorldFactExtract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(description="Short snake_case key, e.g. 'era', 'location:chrachen', 'institution:amt'.")
    value: str = Field(description="The fact about the world as the prose states it.")
    evidence: str = Field(description="The short phrase from the draft that carries it.")


class TimelineExtract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Stable snake_case id for the event, unique, e.g. 'ch03_confession'.")
    when: str = Field(description="Free-text time token, e.g. 'ch3 night', 'the morning after'.")
    event: str = Field(description="What happened, factually. One sentence.")
    involves: List[str] = Field(description="Canon character ids involved. Ids, never names.")
    evidence: str = Field(description="The short phrase from the draft that carries it.")


class ContradictionExtract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canon_ref: str = Field(description="What in the slice is contradicted: a character id, 'world:<key>', a timeline id.")
    canon_says: str = Field(description="What the canon slice states, quoted from the slice.")
    prose_says: str = Field(description="What the draft states instead.")
    evidence: str = Field(description="The short phrase from the draft that contradicts canon.")


class LedgerObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="The motif or promise id from the assignment list.")
    kind: LedgerKind = Field(description="Which assignment this observation answers.")
    landed: bool = Field(
        description="TRUE only if the text really does this on the page. A motif that is merely "
        "alluded to has not been set up; a promise the narrator says will be answered has not been kept."
    )
    evidence: str = Field(
        description="If it landed: the phrase in the draft that delivers it. If it did not: one "
        "sentence on what is missing."
    )


class ChapterExtraction(BaseModel):
    """Everything stage 6 needs from the draft. ONE call — v1's second extraction pass is F3."""

    model_config = ConfigDict(extra="forbid")

    character_facts: List[CharacterFactExtract] = Field(
        description="Facts about canon characters that the draft establishes. Only what the text "
        "actually asserts — not what a reader might infer."
    )
    aliases: List[AliasExtract] = Field(
        description="Every surface form the draft used for a canon character, including ones already "
        "listed in the slice."
    )
    world_facts: List[WorldFactExtract] = Field(description="Facts about the world, setting, places or institutions.")
    timeline: List[TimelineExtract] = Field(description="Events that happened, in this chapter or reported as past.")
    contradictions: List[ContradictionExtract] = Field(
        description="Everything in the draft that disagrees with the canon slice. REPORT them; do "
        "not resolve them, do not pick a winner, do not invent a fact that makes both true."
    )
    ledger: List[LedgerObservation] = Field(
        description="Exactly one observation per assigned setup, payoff, promise-made and "
        "promise-kept listed in the assignment block."
    )


# --------------------------------------------------------------------------------------------
# Decisions
# --------------------------------------------------------------------------------------------

class PromotionKind(str, Enum):
    CHARACTER_FACT = "character_fact"
    ALIAS = "alias"
    WORLD_FACT = "world_fact"
    TIMELINE = "timeline"


class FlagKind(str, Enum):
    CONTRADICTION = "contradiction"              # prose disagrees with canon — adjudicate, never overwrite
    ALIAS_COLLISION = "alias_collision"          # a name another character already owns (F7/F10)
    NAME_DRIFT = "name_drift"                    # the prose called a character something canon does not know
    UNKNOWN_CHARACTER = "unknown_character"      # extraction referenced an id canon has no record of
    UNRESOLVED_REFERENCE = "unresolved_reference"  # an event we refuse to promote because a ref dangles
    LEDGER_UNKNOWN = "ledger_unknown"            # the spec assigned an id the ledger does not contain
    LEDGER_MISSING = "ledger_missing"            # assigned setup/payoff/promise never landed in the prose
    LEDGER_ORDER = "ledger_order"                # payoff before setup / kept before made


@dataclass
class Promotion:
    """One fact that entered canon from this chapter."""

    kind: PromotionKind
    ref: str        # 'stettler.secret', 'world:era', 'alias:rutz', a timeline id
    value: str
    evidence: str = ""


@dataclass
class Flag:
    """One thing the draft raised that canon did NOT absorb. Terminal here; adjudicated in P5."""

    kind: FlagKind
    ref: str
    reason: str
    canon_says: str = ""
    prose_says: str = ""
    evidence: str = ""


@dataclass
class LedgerUpdate:
    id: str
    kind: str            # 'motif' | 'promise'
    chapter: int
    from_status: str
    to_status: str
    note: str = ""


class ReconcileFailed(GateFailed):
    """Reconciling this chapter would have left canon structurally broken. Canon is not written."""


@dataclass
class ReconcileResult:
    canon: StoryModel                                       # updated, NOT committed — the pipeline commits
    promoted: List[Promotion] = field(default_factory=list)
    flagged: List[Flag] = field(default_factory=list)
    ledger_updates: List[LedgerUpdate] = field(default_factory=list)
    issues: List[Issue] = field(default_factory=list)
    extraction: Optional[ChapterExtraction] = None

    @property
    def is_valid(self) -> bool:
        """
        True iff the *resulting canon* is structurally sound.

        Flags deliberately do not count: an unresolved contradiction means canon was protected, not
        that reconciling failed. Only a canon we would be poisoning fails this stage.
        """
        return not blocking(self.issues)


# --------------------------------------------------------------------------------------------
# Normalisation helpers (same spirit as stage 2's draft → canon step)
# --------------------------------------------------------------------------------------------

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(value: str) -> str:
    return _SLUG_RE.sub("_", value.strip().lower()).strip("_")


def _norm(value: str) -> str:
    return " ".join(value.strip().lower().split())


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
    if ref and _slug(ref) in canon.characters:
        return _slug(ref)
    return canon.resolve_name(surface_name) if surface_name.strip() else None


# --------------------------------------------------------------------------------------------
# Prompt
# --------------------------------------------------------------------------------------------

def assignment_block(chapter: int, canon: StoryModel, spec: ChapterSpec) -> str:
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

{assignment_block(chapter, canon, spec)}

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
- A fact the slice already states is NOT a contradiction and does not need reporting as new — but
  reporting it again is harmless, it will be recognised.
- For the ledger: `landed` is about the page, not the plan. If the chapter was told to pay a motif
  off and the payoff is not in the text, say landed=false and name what is missing."""


# --------------------------------------------------------------------------------------------
# Stage
# --------------------------------------------------------------------------------------------

async def reconcile_chapter(
    *,
    chapter: int,
    draft_text: str,
    canon: StoryModel,
    spec: ChapterSpec,
    llm: StructuredLLM,
    tracer: Optional[Tracer] = None,
    model: str = "sonnet",
    strict: bool = True,
    max_tokens: int = 16000,
) -> ReconcileResult:
    """
    Extract what chapter `chapter` established, promote what is new, flag what disagrees.

    The returned canon is a *copy*: the canon handed in is never mutated, so a caller that decides
    not to accept the reconcile still holds the untouched original. Nothing is written to disk —
    the pipeline layer decides when to `commit_canon`.
    """
    tracer = tracer or Tracer(None)
    stage = f"ch{chapter:02d}_reconcile"

    prompt = _extraction_prompt(chapter, draft_text, canon, spec)
    extraction = await llm.parse(
        prompt=prompt, schema=ChapterExtraction, system=SYSTEM, model=model, max_tokens=max_tokens
    )
    tracer.record(stage, prompt=prompt, system=SYSTEM, model=model, artifact=extraction)

    working = canon.model_copy(deep=True)
    promoted: List[Promotion] = []
    flagged: List[Flag] = []

    _promote_aliases(working, extraction, promoted, flagged)
    _promote_character_facts(working, extraction, promoted, flagged)
    _promote_world_facts(working, extraction, promoted, flagged)
    _promote_timeline(working, extraction, chapter, promoted, flagged)

    for c in extraction.contradictions:
        flagged.append(Flag(
            kind=FlagKind.CONTRADICTION,
            ref=c.canon_ref,
            reason=f"the draft contradicts canon at '{c.canon_ref}' — canon stands until adjudicated",
            canon_says=c.canon_says,
            prose_says=c.prose_says,
            evidence=c.evidence,
        ))

    ledger_updates = _update_ledger(working, extraction, spec, chapter, flagged)

    issues = validate(working)
    issues += [
        Issue(f"reconcile.{f.kind.value}", Severity.WARNING, f.reason, f.ref) for f in flagged
    ]

    result = ReconcileResult(
        canon=working,
        promoted=promoted,
        flagged=flagged,
        ledger_updates=ledger_updates,
        issues=issues,
        extraction=extraction,
    )

    tracer.record(
        f"{stage}_decisions",
        prompt="",
        model=model,
        artifact={
            "promoted": [asdict(p) for p in promoted],
            "flagged": [asdict(f) for f in flagged],
            "ledger_updates": [asdict(u) for u in ledger_updates],
        },
        note=f"{len(promoted)} promoted, {len(flagged)} flagged, {len(ledger_updates)} ledger updates",
    )

    if strict and not result.is_valid:
        raise ReconcileFailed(blocking(issues))
    return result


# --------------------------------------------------------------------------------------------
# Promotion passes. Each classifies new / consistent / contradiction and NEVER overwrites canon.
# --------------------------------------------------------------------------------------------

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

        key = _slug(f.key)
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
            elif _norm(current) != _norm(f.value):
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
        key = _slug(w.key)
        if not key or not w.value.strip():
            continue
        current = canon.world_facts.get(key)
        if current is None:
            canon.world_facts[key] = w.value.strip()
            promoted.append(Promotion(
                kind=PromotionKind.WORLD_FACT, ref=f"world:{key}", value=w.value.strip(), evidence=w.evidence
            ))
        elif _norm(current) != _norm(w.value):
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
    known_events = {_norm(ev.event): ev.id for ev in canon.timeline}
    next_order = max((ev.order or 0 for ev in canon.timeline), default=0)

    for i, t in enumerate(extraction.timeline):
        if not t.event.strip():
            continue
        if _norm(t.event) in known_events:
            continue                                   # consistent — already on the timeline

        tid = _slug(t.id) or f"ch{chapter:02d}_e{i + 1}"
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
        known_events[_norm(t.event)] = tid
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


# --------------------------------------------------------------------------------------------
# Ledger
# --------------------------------------------------------------------------------------------

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
