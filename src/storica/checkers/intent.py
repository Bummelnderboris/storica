"""
The Intent / Meaning checker (DESIGN §6).

The question it answers: *does this unit advance the arc-beats and keep the promises it was
assigned — and does it earn its place?* This is the checker aimed squarely at failure class #2:
coherent but hollow. Structural validity is already proven by the deterministic plan validator
before this runs, so the checker is free to spend its judgement on meaning rather than bookkeeping.

One lens, three seams. It judges the arc (stage 3), each chapter spec (stage 4), and — at chapter
scale only — the prose those plans produced. The question is the same every time: *was the
assignment delivered?* A plan that promises a beat and prose that never carries it are the same
failure caught one seam apart, and the reader that can see the second one is the only reader
positioned to notice a chapter that executed its outline without ever paying it off.

Its trigger and its authority are not its business: `checkers/registry.py` decides where it fires
and what it may do about what it finds. On prose it currently advises rather than blocks, because
it has never been calibrated and vitality is the standing lesson about what an uncalibrated binary
gate does to a book (calibration C6).
"""

from __future__ import annotations


from typing import Optional

from ..authors import AuthorModel
from ..llm import stage_model
from ..canon import StoryModel, canon_slice
from ..plan import ChapterSpec, MacroArc, MacroArcDraft, SceneSpec
from .base import Verdict
from .prose_base import ProseCheckerBase, unit_label
from ..agents import block as agent_block, system as agent_system

# The instructions live in agents/intent.md.
SYSTEM = agent_system("intent")

# In agents/intent.md, section <!-- arc-rubric -->.
ARC_RUBRIC = agent_block("intent", "arc-rubric")

# In agents/intent.md, section <!-- spec-rubric -->.
SPEC_RUBRIC = agent_block("intent", "spec-rubric")


# In agents/intent.md, section <!-- prose-rubric -->.
PROSE_RUBRIC = agent_block("intent", "prose-rubric")


class IntentChecker(ProseCheckerBase):
    """Fresh-context judge for what a unit was assigned to deliver: plans, and chapters."""

    name = "intent"

    SYSTEM = SYSTEM
    DEFAULT_MODEL = stage_model("intent")
    DEFAULT_MAX_TOKENS = 8000

    async def check_macro_arc(
        self, draft: MacroArcDraft, canon: StoryModel, *, author_block: str = ""
    ) -> Verdict:
        prompt = f"""{canon_slice(canon)}

{author_block}

# Unit under review: the macro arc
{draft.model_dump_json(indent=2)}

{ARC_RUBRIC}"""
        return await self.check(prompt=prompt, unit="macro_arc")

    async def check_chapter_spec(
        self, spec: ChapterSpec, canon: StoryModel, arc: MacroArc, *, author_block: str = ""
    ) -> Verdict:
        beats = "\n".join(
            f"- [{b.id}] {b.character_id}: {b.beat} (advances {b.advances})"
            for b in arc.beats_for(spec.chapter)
        ) or "- (none scheduled)"
        act = arc.act_for(spec.chapter)
        tension = next((t for t in arc.tension_curve if t.chapter == spec.chapter), None)

        prompt = f"""{canon_slice(
            canon,
            character_ids=spec.present_character_ids,
            motif_ids=[*spec.setups, *spec.payoffs],
            promise_ids=[*spec.promises_made, *spec.promises_kept],
        )}

{author_block}

# The assignment this chapter was given by the macro arc
- act: {act.number if act else '?'} — {act.purpose if act else '(no act)'}
- book shape: {arc.shape}
- intended tension: {tension.tension if tension else '?'} ({tension.note if tension else ''})
- beats scheduled for this chapter:
{beats}

# Unit under review: chapter {spec.chapter} spec
{spec.model_dump_json(indent=2)}

{SPEC_RUBRIC}"""
        return await self.check(prompt=prompt, unit=f"ch{spec.chapter:02d}_spec")

    async def check_prose(
        self,
        *,
        prose: str,
        canon: StoryModel,
        spec: ChapterSpec,
        author: AuthorModel,
        scene: Optional[SceneSpec] = None,
        draw: int = 1,
    ) -> Verdict:
        """
        Judge finished prose against its own spec.

        The arc is not in this reader's hands — `ProseChecker` hands it prose, canon and the spec,
        which is the right grounding anyway: the spec *is* the assignment, and the canon slice
        carries the description of every motif and promise it names. Beats are referenced by id,
        as everywhere else in the pipeline.
        """
        scenes = "\n".join(
            f"  - [{s.id}] {s.location} — intent: {s.intent} | turn: {s.turn}" for s in spec.scenes
        ) or "  - (no scenes specced)"
        exit_state = "\n".join(f"  - {f.key}: {f.value}" for f in spec.exit_state) or "  - (none)"
        ledger = ", ".join([
            *(f"set up {m}" for m in spec.setups),
            *(f"pay off {m}" for m in spec.payoffs),
            *(f"make promise {p}" for p in spec.promises_made),
            *(f"keep promise {p}" for p in spec.promises_kept),
        ]) or "(nothing scheduled)"

        prompt = f"""{self.scene_slice(canon, spec, scene)}

# The assignment this chapter was given
- purpose: {spec.purpose}
- beats it must advance (by id): {", ".join(spec.advances_beats) or "(none)"}
- ledger it must deliver: {ledger}
- state that must be true when it closes:
{exit_state}
- scenes it was written from:
{scenes}

# The prose as written
{prose}

{PROSE_RUBRIC}"""
        return await self.check(prompt=prompt, unit=unit_label(spec, scene), draw=draw)
