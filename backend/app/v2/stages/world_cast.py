"""
Stage 2 — World & cast → canon (DESIGN §5).

Reads: premise × brief × author.  Writes: `canon.characters / relationships / world_facts /
timeline / constraints` — structured and validated.

This is the stage that kills the v1 root cause. In v1 the "story bible" was seeded from *prose*,
so one early misreading (the priest logged as a creditor) became permanent and self-propagating
(F6/F9/F10/F11/F12). Here the cast is born as canon with **stable ids and alias lists**, and the
output does not leave this stage until the deterministic validator passes:

    draft (LLM, flat schema) → normalise (ids, aliases, refs) → validate → repair → commit

The repair loop is grounded: the repair agent is handed the exact issue list and the current draft,
so it fixes what is broken instead of inventing a bridging fact.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from ..authors import AuthorModel
from ..brief import Brief
from ..canon import (
    Character,
    CharacterArc,
    CharacterRole,
    Constraints,
    Issue,
    Premise,
    Relationship,
    StoryModel,
    TimelineEvent,
    blocking,
    validate,
)
from ..llm import StructuredLLM
from ..trace import Tracer
from .gate import GateFailed, format_issues, run_gated

SYSTEM = """You are the World & Cast agent of an autonomous novel pipeline.

You emit CANON: the structured, machine-checked source of truth for a novel. You do not write
prose. Everything you emit will be referenced by stable id for the rest of the run, and every
reference is validated — a dangling id or a name that maps to two characters is a hard failure."""


# --------------------------------------------------------------------------------------------
# LLM-facing draft schemas.
# Flat on purpose: structured outputs reject `additionalProperties: <type>`, so no dicts here.
# --------------------------------------------------------------------------------------------

class FactPair(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(description="Short snake_case fact key, e.g. 'profession', 'secret'.")
    value: str = Field(description="The fact, stated as ground truth. No hedging, no prose flourish.")


class ArcDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    want: str = Field(description="The external goal this character pursues.")
    need: str = Field(description="The internal truth they must learn (or fail to).")
    flaw: str = Field(description="What threatens them from inside.")
    trajectory: str = Field(description="How they change — including 'does not change' if that is the point.")


class CharacterDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Stable snake_case id, e.g. 'stettler'. Never a display name.")
    canonical_name: str = Field(description="Full name as it first appears in the book.")
    aliases: List[str] = Field(
        description="EVERY other surface form this character is called: surname alone, title+name, "
        "epithet, nickname. One character owns all of its names."
    )
    role: CharacterRole
    facts: List[FactPair] = Field(description="Everything true about them that the prose must not contradict.")
    arc: ArcDraft


class RelationshipDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    a: str = Field(description="Character id.")
    b: str = Field(description="Character id.")
    type: str = Field(description="Relation from a to b, e.g. 'widow_of', 'creditor_of'.")


class TimelineDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Stable id, e.g. 't1'. Unique.")
    when: str = Field(description="Free-text time token, e.g. '20y prior', 'ch1 night'.")
    event: str = Field(description="What happened, factually.")
    involves: List[str] = Field(description="Character ids involved. Ids, never names.")
    order: int = Field(description="Chronological sort key, ascending. Earliest event = 1.")


class ConstraintsDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: str = Field(description="ISO code the novel is written in, from the brief.")
    forbidden: List[str] = Field(description="Hard 'no' list: the brief's, plus what this author forbids.")
    chapter_count: int = Field(description="Planned chapter count. Use 0 if the brief leaves it open.")


class WorldCastDraft(BaseModel):
    """The full stage-2 output. One call — no second extraction pass (kills F3)."""

    model_config = ConfigDict(extra="forbid")

    characters: List[CharacterDraft]
    relationships: List[RelationshipDraft]
    world_facts: List[FactPair] = Field(
        description="Setting, era, places, institutions — keys like 'setting', 'era', 'location:chrachen'."
    )
    timeline: List[TimelineDraft] = Field(description="Includes events before the novel opens.")
    constraints: ConstraintsDraft


# --------------------------------------------------------------------------------------------
# Draft → canon
# --------------------------------------------------------------------------------------------

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(value: str) -> str:
    s = _SLUG_RE.sub("_", value.strip().lower()).strip("_")
    return s or "unnamed"


def _norm(name: str) -> str:
    return " ".join(name.strip().lower().split())


def _pairs_to_dict(pairs: List[FactPair]) -> Dict[str, str]:
    return {_slug(p.key): p.value for p in pairs if p.key.strip()}


def draft_to_canon(
    draft: WorldCastDraft,
    *,
    premise: Premise,
    author_id: str,
    brief: Optional[Brief] = None,
) -> StoryModel:
    """
    Turn a flat draft into a `StoryModel`, normalising what can be fixed deterministically.

    Two normalisations matter, because they remove whole classes of LLM slip before the validator
    ever sees them: ids are slugified and de-duplicated, and any reference that is not an id but
    *is* a known character name is resolved to that character's id. Anything still dangling is left
    alone on purpose — the validator must see it so the repair agent gets told about it.
    """
    characters: Dict[str, Character] = {}
    id_map: Dict[str, str] = {}   # id as drafted -> id as stored
    name_to_id: Dict[str, str] = {}

    for cd in draft.characters:
        cid = _slug(cd.id or cd.canonical_name)
        if cid in characters:                       # id collision: keep both, disambiguate
            n = 2
            while f"{cid}_{n}" in characters:
                n += 1
            cid = f"{cid}_{n}"
        id_map[cd.id] = cid
        characters[cid] = Character(
            canonical_name=cd.canonical_name,
            aliases=[a for a in cd.aliases if a.strip()],
            role=cd.role,
            facts=_pairs_to_dict(cd.facts),
            arc=CharacterArc(
                want=cd.arc.want or None,
                need=cd.arc.need or None,
                flaw=cd.arc.flaw or None,
                trajectory=cd.arc.trajectory or None,
            ),
        )
        for nm in characters[cid].all_names():
            name_to_id.setdefault(_norm(nm), cid)

    def _ref(value: str) -> str:
        """Resolve a drafted reference to a stored character id, if we can do it safely."""
        if value in id_map:
            return id_map[value]
        slug = _slug(value)
        if slug in characters:
            return slug
        return name_to_id.get(_norm(value), value)  # unresolved refs stay put for the validator

    relationships = [
        Relationship(a=_ref(r.a), b=_ref(r.b), type=r.type) for r in draft.relationships
    ]
    timeline = [
        TimelineEvent(
            id=ev.id,
            when=ev.when,
            event=ev.event,
            involves=[_ref(x) for x in ev.involves],
            order=ev.order,
        )
        for ev in draft.timeline
    ]

    language = draft.constraints.language or (brief.language if brief else "en")
    forbidden = list(dict.fromkeys([*(brief.forbidden if brief else []), *draft.constraints.forbidden]))
    chapter_count = draft.constraints.chapter_count or (brief.chapter_count if brief else None)

    return StoryModel(
        premise=premise,
        author_id=author_id,
        characters=characters,
        relationships=relationships,
        world_facts=_pairs_to_dict(draft.world_facts),
        timeline=timeline,
        constraints=Constraints(
            language=language,
            forbidden=forbidden,
            chapter_count=chapter_count or None,
        ),
    )


# --------------------------------------------------------------------------------------------
# Stage
# --------------------------------------------------------------------------------------------

class CanonGateFailed(GateFailed):
    """The canon still has blocking issues after the repair budget was spent."""


@dataclass
class WorldCastResult:
    model: StoryModel
    issues: List[Issue] = field(default_factory=list)  # everything the validator said, incl. warnings
    repairs: int = 0

    @property
    def is_valid(self) -> bool:
        return not blocking(self.issues)


def _draft_prompt(premise: Premise, brief: Brief, author: AuthorModel) -> str:
    return f"""{brief.prompt_block()}

{author.conception_block()}

# Premise (CANON — already fixed, do not contradict)
- spark: {premise.spark}
- central_question: {premise.central_question}
- thesis: {premise.thesis}
- why_this_author: {premise.why_this_author}

## Task
Emit the world and cast of this novel as canon.

Hard rules — these are validated mechanically and a violation fails the stage:
- Every character gets a stable snake_case id. Ids are never display names.
- List EVERY surface form of a name as an alias of exactly ONE character. If the priest is
  sometimes "Rutz", sometimes "Pfarrer Rutz", sometimes "der Pfarrer", those are all aliases of
  the one character — never a second character. A name owned by two characters is a hard failure.
- Relationships and timeline events reference character IDS, never names.
- Timeline ids are unique; `order` ascends chronologically and includes events before the novel opens.
- Exactly one character has role 'protagonist'.

Content rules:
- Every character must be necessary to the central question. If you cannot say which beat of the
  question a character carries, cut them.
- Facts are the things prose must not contradict: profession, age, secret, physical marks,
  what they owe and to whom. State them flatly.
- One character's arc may be 'does not change' if that is what the thesis argues.
- world_facts carry setting, era, and every named place or institution.
- The timeline must contain whatever happened before the novel opens that the plot depends on."""


def _repair_prompt(draft: WorldCastDraft, issues: List[Issue]) -> str:
    return f"""The canon you produced failed structural validation.

## Blocking issues
{format_issues(issues)}

## Your current draft
{draft.model_dump_json(indent=2)}

## Task
Emit the CORRECTED full draft.

- Fix exactly what the issues name. Do not restructure the story, rename characters, or add
  material to paper over a problem — the story itself was accepted.
- A name collision means two characters claim the same surface form: decide which single character
  owns that name and remove it from the other, or merge them if they were always the same person.
- A dangling reference means an id that no character has: point it at the right existing id.
- Do NOT invent a new character or a new fact to make a broken reference valid."""


async def develop_world_and_cast(
    *,
    premise: Premise,
    brief: Brief,
    author: AuthorModel,
    llm: StructuredLLM,
    tracer: Optional[Tracer] = None,
    model: str = "sonnet",
    max_repairs: int = 2,
    strict: bool = True,
    max_tokens: int = 24000,
) -> WorldCastResult:
    """
    Run stage 2 and return validated canon.

    The deterministic Canon-Consistency gate runs on every attempt; blocking issues trigger a
    grounded repair call, bounded by `max_repairs`. With `strict` (the default) a canon that still
    has blocking issues raises rather than being handed downstream.
    """
    async def evaluate(draft: WorldCastDraft) -> List[Issue]:
        return validate(draft_to_canon(draft, premise=premise, author_id=author.id, brief=brief))

    outcome = await run_gated(
        llm=llm,
        schema=WorldCastDraft,
        system=SYSTEM,
        prompt=_draft_prompt(premise, brief, author),
        repair_prompt=_repair_prompt,
        evaluate=evaluate,
        stage="world_cast",
        model=model,
        max_tokens=max_tokens,
        tracer=tracer,
        max_repairs=max_repairs,
        strict=strict,
        failure=CanonGateFailed,
    )

    draft: WorldCastDraft = outcome.draft  # type: ignore[assignment]
    return WorldCastResult(
        model=draft_to_canon(draft, premise=premise, author_id=author.id, brief=brief),
        issues=outcome.issues,
        repairs=outcome.repairs,
    )
