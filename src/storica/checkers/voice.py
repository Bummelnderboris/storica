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
from ..canon import StoryModel, canon_slice
from ..llm import StructuredLLM
from ..plan import ChapterSpec, SceneSpec
from ..trace import Tracer
from .base import Checker, Verdict

SYSTEM = """You are an Author-Voice checker in an autonomous novel pipeline.

You did not write this prose and you have no memory of how it was produced. You are handed the
author's own steering material and the brief's hard constraints, and you judge the text against
those two things only.

You do NOT rewrite, and you do NOT score. No "voice score", no rating out of ten — a number would
average a forbidden line away against three good pages, which is exactly the failure this pipeline
was rebuilt to remove. Return a verdict with a list of issues:
- 'pass'     — nothing forbidden appears, and the prose belongs to this author.
- 'revise'   — fixable in place; every issue quotes the offending span and names the smallest edit.
- 'escalate' — the assignment cannot be written in this author's voice without breaking canon or the
               brief (e.g. the scene requires exactly what the author's list forbids). Say so in
               `conflict`; do not resolve it yourself.

Stay in your lane. You are NOT a general prose critic. Pacing, plot logic, grammar, sentence variety,
clarity, imagery you happen to dislike — none of that is yours unless the author's steering material
names it. Another reader judges whether the prose makes sense; another judges whether it contradicts
canon. If your issue would read the same for any novel by any author, do not raise it."""

VOICE_RUBRIC = """Judge in this order:

1. **The forbidden list.** Anything from the brief's forbidden list that appears in the prose is a
   BLOCKING issue, no matter how well it is written and no matter what the scene seemed to need.
   That list is ground truth from the brief; it is not yours to weigh against anything. Quote the
   span and name the forbidden entry it violates in `canon_ref`.
2. **The language.** The prose must be written in the target language throughout. Prose in the wrong
   language, or a paragraph that drifts into another one, is BLOCKING.
3. **The author's "steer away" list.** These are the author's hard nos. An instance of one is
   BLOCKING when it is the kind of move the author's material rejects outright — for Dürrenmatt, an
   explanatory-psychology line ("er tat es, weil er Angst hatte"), a sentimental feeling-description,
   a triumphant or just resolution. Quote the span. Drift that merely leans in a forbidden direction
   without arriving there is a WARNING.
4. **The author's "steer toward" list.** Judge presence, not perfection. A WARNING when a move the
   author would obviously have made is missing or is made limply. BLOCKING only when the unit shows
   none of the author's habits anywhere — prose that could have been written by anyone has failed
   the one job this checker has, even if it is competent.
5. **Does it read like them?** Use the impression material as the final sanity check: if a reader who
   knows this author would not recognise them here, say so once, as one issue, with a quote — not as
   a list of stylistic preferences.

How to report:
- `unit`: a quoted span of at most twelve words from the prose, so the repairer can edit exactly that
  sentence. Never "the whole chapter".
- `canon_ref`: the forbidden entry or the nudge line the judgement rests on. Empty if it rests on
  neither — and if it rests on neither, ask yourself whether it is really your issue to raise.
- `fix_hint`: the smallest edit that removes the violation — "cut the explanatory clause and keep the
  gesture", "state the fact, drop the emotion word". Never "rewrite in the author's voice"."""


def _constraints_block(canon: StoryModel) -> str:
    """The brief's hard constraints, restated flatly — these outrank every stylistic judgement."""
    forbidden = "\n".join(f"- {f}" for f in canon.constraints.forbidden) or "- (nothing forbidden)"
    return f"""# Hard constraints from the brief (GROUND TRUTH — not negotiable, not weighable)

## Target language
{canon.constraints.language} — the prose must be in this language from first word to last.

## Forbidden (any appearance in the prose is a blocking issue)
{forbidden}"""


class AuthorVoiceChecker(Checker):
    """Fresh-context reader for one question: is this that author, and is anything forbidden here?"""

    name = "voice"

    def __init__(
        self,
        llm: StructuredLLM,
        *,
        model: str = "sonnet",
        max_tokens: int = 8000,
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
            f"voice_check_{unit}",
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
        # Voice is judged in situ: an aphorism that lands in a confession scene is not the same move
        # in an interrogation, so the reader gets the same canon slice the writer had.
        character_ids = scene.character_ids if scene else spec.present_character_ids
        slice_text = canon_slice(
            canon,
            character_ids=character_ids,
            motif_ids=[*spec.setups, *spec.payoffs],
            promise_ids=[*spec.promises_made, *spec.promises_kept],
        )

        if scene:
            unit = f"ch{spec.chapter:02d}_{scene.id}"
            header = f"""# Unit under review: chapter {spec.chapter}, scene {scene.id}
- location: {scene.location}
- scene intent: {scene.intent}
- scene turn: {scene.turn}
- chapter purpose (context): {spec.purpose}"""
        else:
            unit = f"ch{spec.chapter:02d}"
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

{author.voice_block()}

# What it feels like to read {author.name}
{author.impression}

{header}

# The prose
{prose}

{VOICE_RUBRIC}"""
        return await self.check(prompt=prompt, unit=unit)
