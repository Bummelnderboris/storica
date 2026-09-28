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
from ..canon import Severity, StoryModel, canon_slice
from ..llm import StructuredLLM, stage_model
from ..plan import ChapterSpec, SceneSpec
from ..trace import Tracer
from .base import Decision, Verdict
from .prose_base import ProseCheckerBase, unit_label
from ..agents import block as agent_block, system as agent_system

# The instructions live in agents/vitality.md.
SYSTEM = agent_system("vitality")

# In agents/vitality.md, section <!-- rubric -->.
VITALITY_RUBRIC = agent_block("vitality", "rubric")


# Vitality is graded by DENSITY, not by presence — the one place in this pipeline where a count
# decides a gate, and it needs justifying because v1 died of a threshold.
#
# Measured on a matched pair (calibration/FINDINGS.md C6): the same chapter as written, and with the
# rubric's anti-patterns inserted. Blocking issues per draw:
#
#     as written   2, 2, 4      (~790 words → 2.5–5.1 per 1000)
#     flattened   15, 15, 13    (~800 words → 16–19 per 1000)
#
# The signal separates cleanly. The *binary* does not: good prose also has two or three places where
# a sharp reader would cut, so "any blocking issue → repair" fires on every chapter ever written.
# Shipping that would have sent everything into the repair loop — the step that flattens prose — so
# the checker would have manufactured the failure it exists to prevent.
#
# This is not v1's averaged quality score. Nothing is averaged and nothing is scored: every issue is
# still located, specific and independently actionable. The threshold only answers "is this a chapter
# with a few soft spots, or a chapter that is dead throughout?" — a question about how much, which a
# count is the honest way to ask.
VITALITY_BLOCK_PER_1000_WORDS = 8.0
VITALITY_MIN_BLOCKING = 3


class VitalityChecker(ProseCheckerBase):
    """Fresh-context reader for inertness. The only checker that fails prose for playing it safe."""

    name = "vitality"
    SYSTEM = SYSTEM
    DEFAULT_MODEL = stage_model("vitality")
    DEFAULT_MAX_TOKENS = 6000

    def __init__(
        self,
        llm: StructuredLLM,
        *,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        tracer: Optional[Tracer] = None,
        block_per_1000_words: float = VITALITY_BLOCK_PER_1000_WORDS,
        min_blocking: int = VITALITY_MIN_BLOCKING,
    ):
        super().__init__(llm, model=model, max_tokens=max_tokens, tracer=tracer)
        self.block_per_1000_words = block_per_1000_words
        self.min_blocking = min_blocking

    def _apply_density_gate(self, verdict: Verdict, prose: str) -> Verdict:
        """
        Keep every finding; block only when they are dense enough to mean the unit is inert.

        Below the threshold the issues are demoted to warnings rather than dropped: they are real
        observations, and a later reader (or a human) may still want them. They simply do not justify
        a repair pass, because a repair pass costs more life than two soft sentences do.
        """
        blocking = verdict.blocking_issues()
        words = max(len(prose.split()), 1)
        density = len(blocking) * 1000 / words

        if len(blocking) >= self.min_blocking and density >= self.block_per_1000_words:
            return verdict

        demoted = [
            i.model_copy(update={"severity": Severity.WARNING}) if i in blocking else i
            for i in verdict.issues
        ]
        return verdict.model_copy(update={
            "decision": Decision.PASS,
            "issues": demoted,
            "summary": (
                f"{verdict.summary} [{len(blocking)} soft spots, {density:.1f}/1000 words — "
                f"below the {self.block_per_1000_words}/1000 inertness threshold]"
            ),
        })

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

        unit = unit_label(spec, scene)

        if scene:
            assignment = f"""# Unit: chapter {spec.chapter}, scene {scene.id}
- what this scene is FOR: {scene.intent}
- what must change in it: {scene.turn}"""
        else:
            assignment = f"""# Unit: chapter {spec.chapter} — {spec.title}
- what this chapter is FOR: {spec.purpose}"""

        prompt = f"""{slice_text}

{assignment}

# Author: {author.name}
{author.impression or "(no impression recorded)"}

# The prose
{prose}

{VITALITY_RUBRIC}"""
        return self._apply_density_gate(await self.check(prompt=prompt, unit=unit, draw=draw), prose)
