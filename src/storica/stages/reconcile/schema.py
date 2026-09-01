"""
What stage 6 asks the model for, and what it hands back to the pipeline.

The extraction schema is flat, every field required, and contains no dicts — the three rules
Anthropic's structured outputs impose (see `storica/llm.py`). Ids and keys are carried explicitly
in lists and mapped into canon's dicts in Python, which is also why `surface_name` exists: the model
reports the name the *prose* used, verbatim, and the mapping onto a canon id happens where we can
see it fail rather than inside the model's head.

`Promotion` / `Flag` / `LedgerUpdate` are the three things reconciliation can conclude about any
one item, and they are dataclasses rather than models because nothing sends them to a model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from ...canon import Issue, StoryModel, blocking
from ..gate import GateFailed

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
    """
    One thing the draft raised that canon did NOT absorb.

    Terminal in this stage by design. `pipeline.adjudicate_flags` then rules on the two kinds that
    are a genuine dispute about what is true — CONTRADICTION and ALIAS_COLLISION — and leaves the
    rest as a planning problem for the next chapter.
    """

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
