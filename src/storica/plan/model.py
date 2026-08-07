"""
The plan: `02_plan/macro_arc.json` and `02_plan/chapters/chNN.spec.json` (DESIGN §5, stages 3–4).

The plan is not canon — it is *intent*, expressed strictly by reference to canon. Every character,
motif and promise appears as an **id**, never as a name or a restated description, so a plan can
never quietly disagree with the canon it points at (that disagreement was root cause #1).

These models are used **both** as the LLM output schema and as the persisted artifact, so what the
agent emits is exactly what lands on disk — no lossy translation step in between. That means they
obey the structured-output rules: `extra="forbid"`, every field required, no dict fields.

The drafts (`MacroArcDraft`) carry the motif/promise *definitions*; those are promoted into canon
(the ledger's home, §4) and the stored `MacroArc` keeps only their ids.
"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, ConfigDict, Field


class Act(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: int = Field(description="1-based act number.")
    title: str = Field(description="Short label for what this act does.")
    chapters: List[int] = Field(description="Chapter numbers in this act. Acts must partition all chapters.")
    purpose: str = Field(description="What must be true by the end of this act that was not true before.")


class TurningPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Stable id, e.g. 'tp1'.")
    chapter: int = Field(description="Chapter it lands in.")
    description: str = Field(description="What irreversibly changes.")
    reverses: str = Field(description="The expectation or position this overturns. A turn that reverses nothing is not one.")


class ArcBeat(BaseModel):
    """One step of one character's arc, pinned to one chapter."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Stable id, e.g. 'b3'.")
    character_id: str = Field(description="Canon character id. Never a name.")
    chapter: int = Field(description="The chapter that must deliver this beat.")
    beat: str = Field(description="What changes for this character here, concretely.")
    advances: str = Field(description="Which arc element this moves: want, need, flaw, or trajectory.")


class TensionPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chapter: int
    tension: int = Field(description="Intended pressure at this chapter, 1 (low) to 10 (peak).")
    note: str = Field(description="What produces the pressure here.")


class MotifDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Stable snake_case id, e.g. 'formula_echo'.")
    desc: str = Field(description="The concrete recurring thing — an image, an object, a repeated phrase.")
    setup_ch: int = Field(description="Chapter it is planted in.")
    payoff_ch: int = Field(description="Chapter it pays off in. Must be >= setup_ch.")


class PromiseDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Stable snake_case id, e.g. 'berta_question'.")
    desc: str = Field(description="What the reader is promised — a question raised, a threat made, a debt owed.")
    made_ch: int = Field(description="Chapter the promise is made in.")
    kept_ch: int = Field(description="Chapter it is kept in. Use 0 if it is deliberately left unresolved.")


class MacroArcDraft(BaseModel):
    """Stage 3 output as the agent emits it: schedule included."""

    model_config = ConfigDict(extra="forbid")

    chapter_count: int = Field(description="Total chapters. Must match canon constraints when those set one.")
    shape: str = Field(description="The arc in two sentences: the movement the whole book performs.")
    acts: List[Act]
    turning_points: List[TurningPoint]
    arc_beats: List[ArcBeat]
    motifs: List[MotifDraft] = Field(description="The setup->payoff schedule. Every motif must pay off or be cut.")
    promises: List[PromiseDraft] = Field(description="Every promise the book makes to the reader, and where it is kept.")
    tension_curve: List[TensionPoint] = Field(description="Exactly one entry per chapter, in order.")


class MacroArc(BaseModel):
    """Stage 3 artifact as stored: the ledger lives in canon, referenced here by id only."""

    model_config = ConfigDict(extra="forbid")

    chapter_count: int
    shape: str
    acts: List[Act]
    turning_points: List[TurningPoint]
    arc_beats: List[ArcBeat]
    motif_ids: List[str] = Field(description="Ids of the motifs scheduled into canon by this arc.")
    promise_ids: List[str] = Field(description="Ids of the promises scheduled into canon by this arc.")
    tension_curve: List[TensionPoint]

    def beats_for(self, chapter: int) -> List[ArcBeat]:
        return [b for b in self.arc_beats if b.chapter == chapter]

    def act_for(self, chapter: int) -> Act | None:
        return next((a for a in self.acts if chapter in a.chapters), None)

    def beat_ids(self) -> set[str]:
        return {b.id for b in self.arc_beats}


class StateFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(description="What the fact is about, e.g. 'stettler:knows' or 'body:location'.")
    value: str = Field(description="The canonical state, stated flatly.")


class SceneSpec(BaseModel):
    """Scene-level planning — the granularity floor (DESIGN risk 3: no paragraph pre-planning)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Stable id, e.g. 's1'.")
    location: str = Field(description="Where it happens. Use a world_fact key when one exists.")
    character_ids: List[str] = Field(description="Canon ids present in this scene. Must be a subset of the chapter's cast.")
    intent: str = Field(description="What this scene is FOR — the work it does that no other scene does.")
    turn: str = Field(description="What is different at the end of the scene than at its start. A scene with no turn is cut.")


class ChapterSpec(BaseModel):
    """Stage 4 artifact: elaborated just-in-time from canon + macro arc for exactly one chapter."""

    model_config = ConfigDict(extra="forbid")

    chapter: int
    title: str
    purpose: str = Field(description="Why this chapter exists. If it advances nothing, it does not exist.")
    pov_character_id: str = Field(description="Canon id of the POV character. Must also appear in present_character_ids.")
    present_character_ids: List[str] = Field(description="Every canon character who appears.")
    advances_beats: List[str] = Field(description="Arc beat ids this chapter must deliver. Exactly those scheduled for it.")
    setups: List[str] = Field(description="Motif ids planted here.")
    payoffs: List[str] = Field(description="Motif ids delivered here.")
    promises_made: List[str] = Field(description="Promise ids made here.")
    promises_kept: List[str] = Field(description="Promise ids kept here.")
    entry_state: List[StateFact] = Field(description="Canonical state as the chapter opens.")
    exit_state: List[StateFact] = Field(description="Canonical state as it closes. The next chapter's entry state.")
    scenes: List[SceneSpec]
