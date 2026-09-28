"""
The Author-Voice checker (DESIGN §6).

Two questions, in this order: **is anything here on the forbidden list?** and **is this the author's
voice?** The first is not a matter of taste — `constraints.forbidden` comes from the brief, which is
immutable ground truth (principle 5), so a violation is blocking however well the sentence is
written. The second is judged against *this* author's steer-toward / steer-away nudges, never
against general craft advice.

The failure mode to avoid is a checker that drifts into being a prose critic. v1's critic scored
"voice" alongside pacing, imagery and dialogue and averaged the lot into a number that competent
drafts always passed (F8); the one line it should have caught — explanatory psychology, a hard "no"
on Dürrenmatt's list — went through untouched. So this reader is deliberately narrow: it flags what
the author's list forbids and what the author's list wants and is missing, and it says nothing about
whether the prose is any good.
"""

from __future__ import annotations

from typing import Optional

from ..authors import AuthorModel
from ..llm import stage_model
from ..canon import StoryModel
from ..plan import ChapterSpec, SceneSpec
from .base import Verdict
from .prose_base import ProseCheckerBase, unit_label
from ..agents import block as agent_block, system as agent_system

# The instructions live in agents/voice.md.
SYSTEM = agent_system("voice")

# In agents/voice.md, section <!-- rubric -->.
VOICE_RUBRIC = agent_block("voice", "rubric")


def _constraints_block(canon: StoryModel) -> str:
    """The brief's hard constraints, restated flatly — these outrank every stylistic judgement."""
    forbidden = "\n".join(f"- {f}" for f in canon.constraints.forbidden) or "- (nothing forbidden)"
    return f"""# Hard constraints from the brief (GROUND TRUTH — not negotiable, not weighable)

## Target language
{canon.constraints.language} — the prose must be in this language from first word to last.

## Forbidden (any appearance in the prose is a blocking issue)
{forbidden}"""


class AuthorVoiceChecker(ProseCheckerBase):
    """Fresh-context reader for one question: is this that author, and is anything forbidden here?"""

    name = "voice"

    SYSTEM = SYSTEM
    DEFAULT_MODEL = stage_model("voice")
    DEFAULT_MAX_TOKENS = 8000

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
        # Voice is judged in situ: an aphorism that lands in a confession scene is not the same move
        # in an interrogation, so the reader gets the same canon slice the writer had.
        slice_text = self.scene_slice(canon, spec, scene)
        unit = unit_label(spec, scene)

        if scene:
            header = f"""# Unit under review: chapter {spec.chapter}, scene {scene.id}
- location: {scene.location}
- scene intent: {scene.intent}
- scene turn: {scene.turn}
- chapter purpose (context): {spec.purpose}"""
        else:
            scenes = "\n".join(
                f"  - [{s.id}] {s.location} — intent: {s.intent} | turn: {s.turn}" for s in spec.scenes
            ) or "  - (no scenes specced)"
            header = f"""# Unit under review: chapter {spec.chapter} — {spec.title}
- chapter purpose: {spec.purpose}
- POV: {spec.pov_character_id}
- scenes it was written from:
{scenes}"""

        prompt = f"""{slice_text}

{_constraints_block(canon)}

{author.writer_block()}

{header}

# The prose
{prose}

{VOICE_RUBRIC}"""
        return await self.check(prompt=prompt, unit=unit, draw=draw)
