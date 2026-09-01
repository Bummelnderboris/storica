"""
The Intent / Meaning checker (DESIGN §6).

The question it answers: *does this unit advance the arc-beats and keep the promises it was
assigned — and does it earn its place?* This is the checker aimed squarely at failure class #2:
coherent but hollow. Structural validity is already proven by the deterministic plan validator
before this runs, so the checker is free to spend its judgement on meaning rather than bookkeeping.

It judges plan units (stages 3 and 4). Prose has its own four readers — canon-consistency,
micro-sense, author-voice and vitality — assembled by `checkers/defaults.py`.
"""

from __future__ import annotations


from ..llm import stage_model
from ..canon import StoryModel, canon_slice
from ..plan import ChapterSpec, MacroArc, MacroArcDraft
from .base import Checker, Verdict

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


class IntentChecker(Checker):
    """Fresh-context judge for plan units."""

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
