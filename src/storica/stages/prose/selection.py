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
from ...agents import block as agent_block, system as agent_system

# The instructions live in agents/selection.md.
SELECTION_SYSTEM = agent_system("selection")

# In agents/selection.md, section <!-- rubric -->.
SELECTION_RUBRIC = agent_block("selection", "rubric")


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
