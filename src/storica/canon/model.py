"""
Canon data model — the single structured source of truth for a novel (Storica v2).

Design (see /DESIGN.md §4):
- Characters are keyed by STABLE IDs, never by display-name strings.
- Every character carries an alias list so name variants resolve to one id (kills F7 fragmentation).
- Motifs and promises form a ledger with `status`, so "meaning" is checkable (setup -> payoff / made -> kept).
- Nothing here is prose-of-record; prose is generated FROM canon and reconciled back INTO it.

`extra="forbid"` everywhere: canon must be strict, so schema drift is caught at parse time.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class CharacterRole(str, Enum):
    PROTAGONIST = "protagonist"
    ANTAGONIST = "antagonist"
    SUPPORTING = "supporting"
    BACKGROUND = "background"


class MotifStatus(str, Enum):
    PLANNED = "planned"      # scheduled, not yet placed
    SETUP = "setup"          # planted in the text
    PAID_OFF = "paid_off"    # delivered
    DROPPED = "dropped"      # deliberately abandoned


class PromiseStatus(str, Enum):
    OPEN = "open"
    KEPT = "kept"
    BROKEN = "broken"        # includes deliberate non-resolution when intended


class CharacterArc(BaseModel):
    model_config = ConfigDict(extra="forbid")
    want: Optional[str] = None        # external goal pursued
    need: Optional[str] = None        # internal truth to learn
    flaw: Optional[str] = None        # what threatens them
    trajectory: Optional[str] = None  # how they change (or fail to)


class Character(BaseModel):
    model_config = ConfigDict(extra="forbid")
    canonical_name: str
    aliases: List[str] = Field(default_factory=list)
    role: CharacterRole = CharacterRole.SUPPORTING
    facts: Dict[str, str] = Field(default_factory=dict)
    arc: Optional[CharacterArc] = None

    def all_names(self) -> List[str]:
        """Canonical name plus every alias — the surface forms that must resolve to this id."""
        return [self.canonical_name, *self.aliases]


class Relationship(BaseModel):
    model_config = ConfigDict(extra="forbid")
    a: str    # character id
    b: str    # character id
    type: str  # e.g. "widow_of", "friend_of", "creditor_of", "concealed_death_of"


class TimelineEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    when: str                                        # free-text token, e.g. "20y prior", "ch1 night"
    event: str
    involves: List[str] = Field(default_factory=list)  # character ids
    order: Optional[int] = None                      # optional explicit sort key for sanity checks


class Motif(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    desc: str
    setup_ch: Optional[int] = None
    payoff_ch: Optional[int] = None
    status: MotifStatus = MotifStatus.PLANNED


class Promise(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    desc: str
    made_ch: Optional[int] = None
    kept_ch: Optional[int] = None
    status: PromiseStatus = PromiseStatus.OPEN


class Awareness(str, Enum):
    """What one character holds about one fact."""

    KNOWS = "knows"
    SUSPECTS = "suspects"
    UNAWARE = "unaware"
    BELIEVES_FALSE = "believes_false"  # holds a specific wrong version — see Knowing.instead


class Knowing(BaseModel):
    """One character's relation to one fact, and since when."""

    model_config = ConfigDict(extra="forbid")
    character_id: str
    awareness: Awareness = Awareness.UNAWARE
    since: str = ""    # timeline id ('t1') or chapter token ('ch2'); empty means "from the start"
    instead: str = ""  # required for believes_false: the wrong thing they hold to be true


class KnowledgeItem(BaseModel):
    """
    One fact, plus the distribution of who holds it.

    Facts live in `Character.facts` and `world_facts`; this records *who has access to them*. In a
    story built on a concealed secret the plot IS this distribution — the tension in a scene is the
    gap between what the reader knows, what the POV character knows, and what the person across the
    table knows. v1 had no representation for it, so a writer had no way to know that a character
    must not yet allude to something, and no checker could catch it when they did.
    """

    model_config = ConfigDict(extra="forbid")
    id: str
    fact: str = Field(description="What is known, stated flatly and in one sentence.")
    concerns: List[str] = Field(
        default_factory=list,
        description="Canon ids this fact is about — character ids, timeline ids, world_fact keys.",
    )
    holders: List[Knowing] = Field(
        default_factory=list,
        description="Every character whose relation to this fact is established. Anyone absent is "
        "treated as unaware.",
    )

    def awareness_of(self, character_id: str) -> Awareness:
        """What `character_id` holds about this fact. Absence means unaware — silence is not knowledge."""
        for h in self.holders:
            if h.character_id == character_id:
                return h.awareness
        return Awareness.UNAWARE


class Premise(BaseModel):
    model_config = ConfigDict(extra="forbid")
    spark: str = ""
    central_question: str = ""
    thesis: str = ""
    why_this_author: str = ""


class Constraints(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: str = "en"
    forbidden: List[str] = Field(default_factory=list)
    chapter_count: Optional[int] = None


class StoryModel(BaseModel):
    """
    The canon. Versioned; every accepted change bumps `version` and snapshots to `history/`.

    Characters are a dict keyed by stable id; everything else references those ids.
    """

    model_config = ConfigDict(extra="forbid")

    premise: Premise = Field(default_factory=Premise)
    author_id: str = ""
    characters: Dict[str, Character] = Field(default_factory=dict)  # id -> Character
    relationships: List[Relationship] = Field(default_factory=list)
    world_facts: Dict[str, str] = Field(default_factory=dict)
    timeline: List[TimelineEvent] = Field(default_factory=list)
    knowledge: List[KnowledgeItem] = Field(default_factory=list)
    motifs: List[Motif] = Field(default_factory=list)
    promises: List[Promise] = Field(default_factory=list)
    constraints: Constraints = Field(default_factory=Constraints)
    version: int = 1

    def character_ids(self) -> set[str]:
        return set(self.characters.keys())

    def knowledge_for(self, character_id: str) -> List[tuple["KnowledgeItem", Awareness]]:
        """Every knowledge item paired with what `character_id` holds about it."""
        return [(k, k.awareness_of(character_id)) for k in self.knowledge]

    def knows(self, character_id: str, knowledge_id: str) -> bool:
        """True only for full knowledge. Suspicion is not knowledge and must not be written as it."""
        item = next((k for k in self.knowledge if k.id == knowledge_id), None)
        return item is not None and item.awareness_of(character_id) == Awareness.KNOWS

    def resolve_name(self, name: str) -> Optional[str]:
        """Return the character id that owns `name` (canonical or alias), case-insensitively."""
        key = " ".join(name.strip().lower().split())
        for cid, ch in self.characters.items():
            if any(" ".join(n.strip().lower().split()) == key for n in ch.all_names()):
                return cid
        return None
