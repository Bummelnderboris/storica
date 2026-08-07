"""
The Vitality checker — the only reader that can fail a unit for being safe.

Every other checker in this pipeline is a **conformance** check: does this match canon, did it hit
its assigned beats, does it sound like the author, are its details grounded. A chapter that
satisfies all four and is completely inert passes the entire gate. Worse, the machinery pushes
toward exactly that chapter: each repair iteration moves prose closer to the rubric and further from
whatever was surprising in it, so the system's natural product is competent, correct and dead.

`DESIGN.md` §10 files this under residual risks — "a plausible-but-flat story the auditor rates
coherent but the creator finds dull". It belongs higher. v1's actual output was *good* sentence by
sentence; what it lacked was never fluency. And the stated goal is a novel that surprises its
creator, while nothing else in the pipeline optimises for surprise and several things suppress it.

So this checker's polarity is inverted:

- it does not ask "is this correct?" — three other readers already did;
- it fails a unit for being predictable, explanatory, or safe;
- its fix hints are almost always **cuts**, which is what makes it safe to pair with the repair
  loop's minimal-edit contract: deleting the sentence that explains the gesture is a small,
  local, non-inventing edit, and it is usually the whole fix.

It never asks for more material. "Add tension" is how a scene gets longer and deader.
"""

from __future__ import annotations

from typing import Optional

from ..authors import AuthorModel
from ..canon import StoryModel, canon_slice
from ..llm import StructuredLLM
from ..plan import ChapterSpec, SceneSpec
from ..trace import Tracer
from .base import Checker, Verdict

SYSTEM = """You are the Vitality reader in an autonomous novel pipeline.

You did not write this prose. Other readers have already checked it against canon, against its
assigned beats, and against the author's voice — assume all of that is handled and do not repeat it.
A factual error is not your business. A correct, competent, lifeless paragraph IS your business, and
you are the only reader who can stop one.

Your default is suspicion, not approval. This pipeline plans everything in advance and then repairs
toward a rubric, and both of those tend to produce prose that executes an outline rather than
imagines a scene. That is the failure you exist to catch. If a passage could have been written by
someone who had read the plan but never pictured the room, say so.

You never ask for additions. Length is not life, and "raise the stakes" or "add tension" produces
longer dead prose. Your fixes are cuts and replacements: the sentence that explains the gesture, the
adjective that tells the reader how to feel, the summary that follows the scene it summarises."""

VITALITY_RUBRIC = """Read the unit and ask, honestly, whether it is alive.

Flag these as BLOCKING:

1. **The explained gesture.** An action, image or line of dialogue immediately followed by its
   interpretation — the sentence that tells the reader what the previous sentence meant. The fix is
   always the same: cut the explanation and let the thing stand. This is the single most common way
   competent prose dies, and it is the easiest to fix.
2. **Announced interiority.** Emotion stated as a fact about a character ("he felt a deep unease",
   "she was afraid") where the scene had the means to enact it. Name what in the scene could have
   carried it instead.
3. **The outline showing through.** A passage that reads as the assignment restated in sentences:
   each paragraph doing its assigned job, in order, with nothing that exceeds the plan. Nothing is
   wrong with it and nothing in it was imagined.
4. **Generic specificity.** Detail that is concrete but interchangeable — the stock cold, the stock
   silence, the furniture that could belong to any room in any book. Detail should be evidence that
   this scene was pictured; if it could be lifted into another novel unchanged, it is filler.
5. **The turn that costs nothing.** Something must be different at the end than at the start, and
   the difference should cost somebody something. A turn that is merely informational — a fact
   delivered, a decision announced — is not a turn.

Flag as WARNING, not blocking:
- rhythm that has gone monotone over several paragraphs (all sentences the same length or shape);
- an image reused from earlier without gaining anything by the repetition;
- a strong opening that decays into summary by the end of the unit.

PASS the unit when it does something you did not expect — even if that thing is odd, even if it is
quiet. Strangeness that is *earned by the situation* is the signal you are looking for. Do not
penalise a scene for being restrained: understatement is not flatness, and in an author who works by
withholding, the flattest-looking page may be the most alive one. Judge whether the withholding is
doing work, not whether the page is loud.

Never escalate. There is no upstream conflict that makes prose dull; that is always the prose.

How to report:
- `unit`: a quoted span of at most twelve words — the exact place the life drains out.
- `kind`: always 'meaning'.
- `canon_ref`: usually empty. This judgement is not grounded in canon and must not pretend to be.
- `fix_hint`: a specific, local, SUBTRACTIVE instruction. "Cut the sentence beginning 'Er spürte'."
  "Delete the final paragraph; the scene ends on the closing door." Never "make it more vivid",
  never "add", never "rewrite the scene"."""


class VitalityChecker(Checker):
    """Fresh-context reader for inertness. The only checker that fails prose for playing it safe."""

    name = "vitality"

    def __init__(
        self,
        llm: StructuredLLM,
        *,
        model: str = "sonnet",
        max_tokens: int = 6000,
        tracer: Optional[Tracer] = None,
    ):
        self.llm = llm
        self.model = model
        self.max_tokens = max_tokens
        self.tracer = tracer or Tracer(None)

    async def check(self, *, prompt: str, unit: str) -> Verdict:
        verdict = await self.llm.parse(
            prompt=prompt,
            schema=Verdict,
            system=SYSTEM,
            model=self.model,
            max_tokens=self.max_tokens,
        )
        self.tracer.record(
            f"vitality_check_{unit}",
            prompt=prompt,
            system=SYSTEM,
            model=self.model,
            artifact=verdict,
            note=verdict.decision.value,
        )
        return verdict

    async def check_prose(
        self,
        *,
        prose: str,
        canon: StoryModel,
        spec: ChapterSpec,
        author: AuthorModel,
        scene: Optional[SceneSpec] = None,
    ) -> Verdict:
        # A deliberately thin slice: premise and constraints only, no character facts or timeline.
        # This reader must not start checking consistency — that is someone else's job, and handing
        # it the full canon is an invitation to do the easier task instead of the one it is for.
        slice_text = canon_slice(
            canon,
            character_ids=[],
            motif_ids=[],
            promise_ids=[],
            include_timeline=False,
            include_premise=True,
        )

        if scene:
            unit = f"ch{spec.chapter:02d}_{scene.id}"
            assignment = f"""# Unit: chapter {spec.chapter}, scene {scene.id}
- what this scene is FOR: {scene.intent}
- what must change in it: {scene.turn}"""
        else:
            unit = f"ch{spec.chapter:02d}"
            assignment = f"""# Unit: chapter {spec.chapter} — {spec.title}
- what this chapter is FOR: {spec.purpose}"""

        prompt = f"""{slice_text}

{assignment}

# Author: {author.name}
{author.impression or "(no impression recorded)"}

# The prose
{prose}

{VITALITY_RUBRIC}"""
        return await self.check(prompt=prompt, unit=unit)
