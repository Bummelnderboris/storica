"""
Stage 5 — Grounded prose (DESIGN §5, §6, §7).

Reads: one `ChapterSpec` + the **full canon slice** for everything each scene touches.
Writes: the chapter as markdown (the caller persists it to `03_drafts/chNN.md`).

Three v1 failures shape this module, and each one is a rule here rather than a hope:

- **F5 — truncated context.** v1 threaded `raw_blueprint[:800]` into the writer, so a chapter barely
  knew what the previous one decided. Here every scene call carries `canon_slice(...)` for exactly
  the characters, motifs and promises that scene touches: the complete canonical truth about what
  it handles, never a prefix of a summary.
- **F9 — canon drift the critic could not see.** v1's writer recast the priest as a creditor and
  nothing caught it. Here the canon slice is in the prompt as *source of truth*, the writer is
  forbidden from inventing facts, and every checker judging the scene is handed the same slice.
- **F8 — averaging.** Checkers run on the **scene**, not on the chapter, so one hollow scene cannot
  be averaged away by four good ones — and they run again on the assembled chapter, because some
  failures (a repeated image, a turn that lands twice) only exist at chapter scale.

The macro→micro seam (§7) is carried explicitly: the beats to advance and the setups/payoffs to
deliver are named **by id in the prompt**. Intent is stated, never implied — an agent that is only
*hinted* at what a scene is for will write something fluent that is for nothing.

Prose is not schema-shaped, so it cannot use `run_gated`; this module hand-writes the same loop and
keeps its properties: cheap deterministic checks before expensive LLM ones, a bounded repair budget
per unit, and a raise rather than a broken unit passed downstream.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable, List, Optional, Sequence

from ...authors import AuthorModel
from ...canon import Issue, StoryModel, blocking, chapter_unit
from ...checkers.base import Decision, Escalation
from ...checkers.prose_base import ProseChecker
from ...llm import StructuredLLM, stage_model
from ...plan import ChapterSpec, MacroArc, SceneSpec
from ...trace import Tracer
from ..gate import GateFailed
from .prompts import (
    MIN_SCENE_CHARS,
    SCENE_DIVIDER,
    SYSTEM,
    TAIL_CHARS,
    _chapter_slice,
    _language,
    _repair_prompt,
    _scene_prompt,
    _scene_slice,
    _tail,
    scene_assignment_block,
)
from .quality import _deterministic_issues, _repair_loop, _split_scenes, assemble_chapter
from .selection import CandidateChoice, _generate_candidates, _select

__all__ = [
    "write_chapter",
    "ProseResult",
    "ProseGateFailed",
    "assemble_chapter",
    "scene_assignment_block",
    "SCENE_DIVIDER",
    "TAIL_CHARS",
    "MIN_SCENE_CHARS",
    "SYSTEM",
    "CandidateChoice",
]


# The reader whose blocking verdict short-circuits the rest of the gate. The name is the one
# `checkers.with_consensus` keys on, so the consensus wrapper carries it too.
CANON_CONSISTENCY = "canon_consistency"


class ProseGateFailed(GateFailed):
    """A prose unit still had blocking issues when its repair budget ran out."""


@dataclass
class ProseResult:
    chapter: int
    text: str
    scenes: List[str] = field(default_factory=list)
    issues: List[Issue] = field(default_factory=list)
    repairs: int = 0

    @property
    def is_valid(self) -> bool:
        return not blocking(self.issues)


async def write_chapter(
    *,
    spec: ChapterSpec,
    canon: StoryModel,
    arc: MacroArc,
    author: AuthorModel,
    llm: StructuredLLM,
    previous_tail: str = "",
    checkers: Sequence[ProseChecker] = (),
    tracer: Optional[Tracer] = None,
    model: str = stage_model("prose"),
    max_repairs: int = 2,
    strict: bool = True,
    max_tokens: int = 32000,
    min_scene_chars: int = MIN_SCENE_CHARS,
    guidance: str = "",
    n_candidates: int = 1,
    selection_model: str = stage_model("selection"),
) -> ProseResult:
    """
    Write one chapter, scene by scene, grounded in canon and checked at both scales.

    Never one chapter-shaped call: each scene is generated from its own canon slice and its own
    assignment, so what the scene was for is in the prompt that wrote it, and what went wrong in it
    is localised to it.

    `guidance` carries a binding ruling from adjudication (§6.5) into a re-attempt: when a first
    attempt escalated and the adjudicator ruled, the ruling rides into every scene prompt so the
    re-write is bound by it rather than re-discovering the same conflict.
    """
    tracer = tracer or Tracer(None)
    language = _language(canon)
    unit_prefix = chapter_unit(spec.chapter)

    def evaluator(unit: str, scene: Optional[SceneSpec]) -> Callable[[str], Awaitable[List[Issue]]]:
        async def evaluate(text: str) -> List[Issue]:
            issues = _deterministic_issues(text, unit, min_scene_chars)
            if issues:
                return issues  # a stub is not worth a checker call
            for checker in checkers:
                verdict = await checker.check_prose(
                    prose=text, canon=canon, spec=spec, author=author, scene=scene
                )
                if verdict.decision == Decision.ESCALATE:
                    raise Escalation(unit, verdict.conflict, verdict)
                issues += verdict.to_issues(checker.name)
                if checker.name == CANON_CONSISTENCY and blocking(issues):
                    # A contradiction makes the other judgements moot (checkers/defaults.py): no
                    # point paying to polish the texture of a paragraph that says the wrong man
                    # signed the certificate. The rest run on the repaired text.
                    break
            return issues
        return evaluate

    scenes: List[str] = []
    issues: List[Issue] = []
    repairs = 0
    tail = previous_tail
    previous_is_chapter = True

    for index, scene in enumerate(spec.scenes, start=1):
        unit = f"{unit_prefix}_{scene.id}"
        prompt = _scene_prompt(
            spec=spec, canon=canon, arc=arc, author=author, scene=scene,
            index=index, previous_tail=tail, previous_is_chapter=previous_is_chapter,
            guidance=guidance,
        )
        if n_candidates > 1:
            # Selection before repair. Repair moves a draft toward the rubric, which is exactly what
            # makes prose grey — every iteration trades surprise for compliance. Choosing among
            # independent drafts preserves the spread instead of collapsing it, so the variance is
            # spent on finding a live scene rather than sanding one down.
            candidates = await _generate_candidates(
                prompt=prompt, n=n_candidates, llm=llm, model=model, max_tokens=max_tokens,
                tracer=tracer, unit=unit, min_chars=min_scene_chars,
            )
            text = await _select(
                candidates=candidates, assignment=prompt, llm=llm,
                model=selection_model, tracer=tracer, unit=unit,
            )
        else:
            text = await llm.generate(prompt=prompt, system=SYSTEM, model=model, max_tokens=max_tokens)
        tracer.record(f"{unit}_prose", prompt=prompt, system=SYSTEM, model=model, artifact=text)

        text, scene_issues, scene_repairs = await _repair_loop(
            stage=f"{unit}_prose",
            unit=f"scene {scene.id}",
            text=text,
            evaluate=evaluator(unit, scene),
            repair_prompt=lambda current, flagged, _s=scene, _p=prompt: _repair_prompt(
                unit=f"scene {_s.id}",
                current=current,
                issues=flagged,
                canon_block=_scene_slice(spec, canon, _s),
                language=language,
                regenerate_prompt=_p,
            ),
            llm=llm, model=model, max_tokens=max_tokens, tracer=tracer, max_repairs=max_repairs,
        )

        repairs += scene_repairs
        issues += scene_issues
        if strict and blocking(scene_issues):
            raise ProseGateFailed(blocking(issues))

        scenes.append(text.strip())
        tail = _tail(text)
        previous_is_chapter = False

    chapter_text = assemble_chapter(spec.title, scenes)
    tracer.record(
        f"{unit_prefix}_prose_assembled",
        prompt="",
        model=model,
        artifact=chapter_text,
        note=f"{len(scenes)} scenes",
    )

    # Some failures only exist at chapter scale — an image used twice, a turn that lands in two
    # scenes, a chapter that adds up to less than its parts. The scene pass cannot see them.
    chapter_text, chapter_issues, chapter_repairs = await _repair_loop(
        stage=f"{unit_prefix}_prose",
        unit=f"chapter {spec.chapter}",
        text=chapter_text,
        evaluate=evaluator(unit_prefix, None),
        repair_prompt=lambda current, flagged: _repair_prompt(
            unit=f"chapter {spec.chapter}",
            current=current,
            issues=flagged,
            canon_block=_chapter_slice(spec, canon),
            language=language,
            regenerate_prompt="",
        ),
        llm=llm, model=model, max_tokens=max_tokens, tracer=tracer, max_repairs=max_repairs,
    )

    repairs += chapter_repairs
    issues += chapter_issues
    if chapter_repairs:
        scenes = _split_scenes(chapter_text) or scenes

    result = ProseResult(
        chapter=spec.chapter, text=chapter_text, scenes=scenes, issues=issues, repairs=repairs
    )
    if strict and not result.is_valid:
        raise ProseGateFailed(blocking(issues))
    return result
