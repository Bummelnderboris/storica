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

SYSTEM = """You are an Intent checker in an autonomous novel pipeline.

You did not write the unit you are judging and you have no memory of how it was produced — judge
only what is in front of you, against the canon slice given.

You do NOT rewrite, and you do NOT score. You return a verdict with a list of issues:
- 'pass'     — the unit advances what it was assigned and earns its place.
- 'revise'   — fixable in place; every issue names the smallest change that fixes it.
- 'escalate' — the assignment itself is unsatisfiable, or the canon contradicts itself. Do not
               invent a bridging fact to make the problem go away; escalate instead.

Mark an issue 'blocking' when the unit cannot proceed as-is. Be sparing with 'blocking' on taste
and generous with it on emptiness: a chapter that advances nothing is blocking, a chapter you would
have written differently is not."""

ARC_RUBRIC = """Judge the arc on:
1. **Does every chapter do work?** Any chapter carrying no beat, no turn, and no ledger event is a
   blocking issue — name the chapter.
2. **Does the arc answer the central question?** The ending must answer it; the middle must make
   the answer uncertain. If the question is settled by the halfway point, that is blocking.
3. **Do the character arcs move?** Every beat must change something for its character. A beat that
   restates a fact rather than changing a state is a blocking issue.
4. **Is the ledger load-bearing?** Each motif's payoff must mean something *because* of its setup;
   each promise must be kept, or deliberately and pointedly broken. Decorative motifs are issues.
5. **Does the shape belong to this author?** Judge against the author's obsessions, not general
   craft advice — a Duerrenmatt arc that resolves justly has failed even if it is well made.
6. **Does the arc honour the brief's constraints and forbidden list?** Violations are blocking."""

SPEC_RUBRIC = """Judge the chapter spec on:
1. **Does it deliver its assignment?** The beats, setups, payoffs and promises listed for this
   chapter must actually be carried by named scenes. A beat with no scene that could deliver it is
   a blocking issue.
2. **Does every scene turn?** A scene whose stated turn does not change the state of anyone in it
   is a blocking issue — name the scene id.
3. **Is the purpose real?** "Introduce the setting", "build tension", "show character" are not
   purposes. What is different about the story after this chapter?
4. **Entry/exit state:** does the exit state reflect what the scenes actually do? A chapter that
   claims a state change no scene produces is blocking.
5. **Is the cast justified?** A character present who does nothing is an issue.
6. **Is anything here contradicted by the canon slice?** Contradiction is blocking; escalate if the
   canon itself is what looks wrong."""


PROSE_RUBRIC = """Judge the chapter against the assignment its spec gave it:

1. **Is every scene's turn on the page?** The spec says what changes in each scene. A scene whose
   stated turn is described rather than enacted, or does not happen at all, is a blocking issue —
   name the scene id and quote the line that was supposed to carry it.
2. **Is the exit state true at the end?** Every exit-state fact must be true of the world when the
   chapter closes, and it must have become true *in this chapter*. A state the prose assumes rather
   than reaches is blocking.
3. **Did the ledger land?** Every motif setup or payoff and every promise this chapter was assigned
   is listed in the canon slice with its description. A payoff the text never delivers, or delivers
   as a mention rather than an event, is blocking — say which, and what is missing.
4. **Is the purpose real on the page?** Something must be different about the story now. If the
   chapter could be cut and the next one still read, that is blocking.
5. **Does it take work that is not its own?** A chapter that pays off a motif scheduled for later,
   or resolves a promise it was not given, is an issue: it leaves the later chapter empty.

You are not the other readers. Say nothing about contradictions with canon, about whether the
sentences are grounded, about the author's voice, or about whether the prose is alive. Four other
readers own those. Yours is the assignment, and only the assignment."""


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
