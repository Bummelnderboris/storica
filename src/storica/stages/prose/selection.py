"""
Selection: draw several independent drafts of a unit and keep the one that is most alive.

Repair is a regression-to-the-mean engine — every iteration moves a draft toward the rubric and away
from whatever was surprising in it — so the variance is better spent choosing than sanding. Cost is
k generate calls plus **one** cheap judgement, not k gates.

The drafts come from the *identical* prompt on purpose. Steering each one toward a different
adjective would make the choice a choice between instructions rather than between imaginations.
"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, ConfigDict, Field

from ...llm import StructuredLLM, gather_draws
from ...trace import Tracer
from .prompts import SYSTEM
from .quality import _deterministic_issues

SELECTION_SYSTEM = """You are the Selector in an autonomous novel pipeline.

Several independent drafts of the same scene were written from the same assignment. You pick one.
You did not write any of them and you have no stake in any of them.

You are NOT checking correctness. Other readers, with the canon in hand, do that after you, and they
can repair small errors in whatever you choose. Picking the tidiest draft is therefore the one
mistake that cannot be undone later: correctness can be added to a living scene, but life cannot be
added to a correct one."""

SELECTION_RUBRIC = """Choose the draft that is most ALIVE.

The pipeline's whole tendency is toward the safe middle, so your bias must run the other way. Prefer:

1. **The one that surprised you.** A move you did not see coming, an image that is odd and exactly
   right, a line of dialogue that answers a question nobody asked. If two drafts are equally
   competent and one startled you, that one.
2. **The one that trusts the reader.** Prose that states the situation and stops, over prose that
   also explains what it means. A gesture left unglossed beats a gesture plus its interpretation.
3. **The one that risks something.** A scene that commits to a strange choice and lives with it, over
   one that hedges. Flatness is a failure mode; awkward ambition usually is not.
4. **The one with the sharper turn.** Something must be different at the end than at the start. Prefer
   the draft where that difference costs somebody something.

Reject: the draft that reads like a summary of the assignment; the one where every sentence does the
job the outline gave it and nothing more; the one whose emotional content is announced rather than
enacted; the one that could have been written from the plan alone without imagining the scene.

Do not prefer a draft for being longer, more ornate, or more eventful. Density is not life. A quiet
scene that is exactly observed beats a loud one that is generic.

Return the index of your choice and one sentence on what the others lacked."""


class CandidateChoice(BaseModel):
    """Which draft survives. One call, regardless of how many candidates there are."""

    model_config = ConfigDict(extra="forbid")

    chosen_index: int = Field(description="0-based index of the chosen draft.")
    reasoning: str = Field(description="One sentence: what this draft has that the others do not.")


async def _generate_candidates(
    *,
    prompt: str,
    n: int,
    llm: StructuredLLM,
    model: str,
    max_tokens: int,
    tracer: Tracer,
    unit: str,
    min_chars: int,
) -> List[str]:
    """
    Draw `n` independent drafts of one unit and drop the ones that are stubs.

    Identical prompts on purpose: the spread comes from sampling, not from asking for "a darker
    version" — steering each draft toward a different adjective would make the choice a choice
    between instructions rather than between imaginations.
    """
    # Drawn concurrently: k independent samples of one prompt have no ordering between them, and
    # under the replay driver each carries its own `draw` index, so a slot is not decided by which
    # request happens to return first. Sequentially this was the single slowest step in a run.
    texts = await gather_draws(
        llm.generate(prompt=prompt, system=SYSTEM, model=model, max_tokens=max_tokens, draw=i + 1)
        for i in range(n)
    )

    candidates: List[str] = []
    for i, text in enumerate(texts):
        tracer.record(
            f"{unit}_prose_candidate_{i}", prompt=prompt, system=SYSTEM, model=model, artifact=text
        )
        if not _deterministic_issues(text, unit, min_chars):
            candidates.append(text)
    # Every draw a stub: keep the last one so the repair loop sees the real failure and reports
    # it, rather than paying for another draw or raising something less informative here.
    return candidates or list(texts[-1:])


async def _select(
    *,
    candidates: List[str],
    assignment: str,
    llm: StructuredLLM,
    model: str,
    tracer: Tracer,
    unit: str,
) -> str:
    """Pick the most alive draft. Falls back to the first on a nonsense index rather than failing."""
    if len(candidates) == 1:
        return candidates[0]

    blocks = "\n\n".join(
        f"## Draft {i}\n{text.strip()}" for i, text in enumerate(candidates)
    )
    prompt = f"""{assignment}

# The drafts
{blocks}

{SELECTION_RUBRIC}"""
    choice = await llm.parse(
        prompt=prompt, schema=CandidateChoice, system=SELECTION_SYSTEM, model=model, max_tokens=2000
    )
    tracer.record(
        f"{unit}_prose_selection",
        prompt=prompt,
        system=SELECTION_SYSTEM,
        model=model,
        artifact=choice,
        note=f"chose {choice.chosen_index} of {len(candidates)}",
    )
    if 0 <= choice.chosen_index < len(candidates):
        return candidates[choice.chosen_index]
    return candidates[0]
