"""
Stage 1 — Conception (DESIGN §5).

Reads: the creator brief × the author model.  Writes: `canon.premise`.

This replaces v1's prose topic+thesis phases. Two calls, two genuinely different decisions:

1. **Generate** a few candidate "stories this author would tell" — the author's question-lines are
   the generator, not a style filter (principle 6). Candidates are structured, never prose.
2. **Choose and sharpen** one, judged against the brief and the author's obsessions.

The output is a `Premise`, which is canon — so no downstream stage ever re-reads prose to find out
what the story is about (root cause #1).
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from ..authors import AuthorModel
from ..brief import Brief
from ..canon import Premise
from ..llm import StructuredLLM, stage_model
from ..trace import Tracer

SYSTEM = """You are the Conception agent of an autonomous novel pipeline.

You do not write prose. You decide WHAT STORY gets told, in the voice of a specific author's
obsessions, and you emit it as structured data. The creator's brief is immutable ground truth:
you may interpret it, never contradict it."""


class PremiseCandidate(BaseModel):
    """One story this author might tell from this brief."""

    model_config = ConfigDict(extra="forbid")

    spark: str = Field(description="The concrete situation the novel starts from, in 1-2 sentences.")
    central_question: str = Field(
        description="The single question the whole novel asks. Must be answerable only by the ending."
    )
    thesis: str = Field(description="What the novel argues about the world. One sentence, no hedging.")
    why_this_author: str = Field(
        description="Which of this author's question-lines/obsessions this story is driven by, and how."
    )
    question_line: str = Field(description="The author question-line this candidate is built on, verbatim.")
    risk: str = Field(description="The most likely way this candidate goes wrong or turns generic.")


class ConceptionCandidates(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidates: List[PremiseCandidate]


class ConceptionChoice(BaseModel):
    """The chosen premise, possibly merged from more than one candidate."""

    model_config = ConfigDict(extra="forbid")

    chosen_index: int = Field(description="0-based index of the candidate this is primarily built on.")
    reasoning: str = Field(description="Why this one, judged against the brief and the author's obsessions.")
    merged_from: List[int] = Field(description="Indices of any other candidates whose ideas were folded in.")
    premise: PremiseCandidate = Field(description="The final, sharpened premise. May improve on the original.")


def _candidates_prompt(brief: Brief, author: AuthorModel, n: int) -> str:
    return f"""{brief.prompt_block()}

{author.conception_block()}

## Task
Propose {n} DISTINCT novels this author would write from this brief.

Rules:
- Each candidate must be driven by a different question-line of the author's. Name it verbatim.
- The central question must be a real question — one the ending answers, not a theme label.
- The thesis must be arguable. If its opposite is absurd, it is not a thesis.
- Do not converge: candidates that differ only in setting are the same candidate.
- Honour the brief's forbidden list absolutely.
- Name the risk honestly — the most likely way each candidate turns generic."""


def _choice_prompt(brief: Brief, author: AuthorModel, candidates: ConceptionCandidates) -> str:
    listing = "\n\n".join(
        f"""### Candidate {i}
- spark: {c.spark}
- central_question: {c.central_question}
- thesis: {c.thesis}
- why_this_author: {c.why_this_author}
- question_line: {c.question_line}
- risk: {c.risk}"""
        for i, c in enumerate(candidates.candidates)
    )
    return f"""{brief.prompt_block()}

{author.conception_block()}

## Candidates
{listing}

## Task
Choose the one novel to write. You may fold the best idea from another candidate into it, and you
should sharpen the wording — the result does not have to be any candidate verbatim.

Judge on:
1. Does it actually ask one of this author's questions, or merely wear their costume?
2. Does it serve the creator's brief and question-lines?
3. Is the central question answerable only by the ending?
4. Does the stated risk look avoidable, or is it baked into the premise?

Record which candidate you built on and which others you merged from."""


async def conceive(
    *,
    brief: Brief,
    author: AuthorModel,
    llm: StructuredLLM,
    tracer: Optional[Tracer] = None,
    n_candidates: int = 3,
    model: str = stage_model("conception"),
) -> Premise:
    """Run stage 1 and return the premise to write into canon."""
    tracer = tracer or Tracer(None)

    gen_prompt = _candidates_prompt(brief, author, n_candidates)
    candidates = await llm.parse(
        prompt=gen_prompt, schema=ConceptionCandidates, system=SYSTEM, model=model
    )
    tracer.record(
        "conception_candidates", prompt=gen_prompt, system=SYSTEM, model=model, artifact=candidates
    )
    if not candidates.candidates:
        raise ValueError("conception produced no candidates")

    choice_prompt = _choice_prompt(brief, author, candidates)
    choice = await llm.parse(
        prompt=choice_prompt, schema=ConceptionChoice, system=SYSTEM, model=model
    )
    tracer.record(
        "conception_choice",
        prompt=choice_prompt,
        system=SYSTEM,
        model=model,
        artifact=choice,
        note=choice.reasoning,
    )

    p = choice.premise
    return Premise(
        spark=p.spark,
        central_question=p.central_question,
        thesis=p.thesis,
        why_this_author=p.why_this_author,
    )
