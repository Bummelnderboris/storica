"""
The cheap deterministic gate, and the bounded repair loop it feeds.

Prose is not schema-shaped, so it cannot use `run_gated`; this is the same loop hand-written, and it
keeps the same two properties that make it safe to run unattended: cheap checks before expensive
ones, and a bounded budget after which the unit raises rather than being passed downstream.
"""

from __future__ import annotations

from typing import Awaitable, Callable, List, Optional, Sequence, Tuple

from ...canon import Issue, Severity, blocking
from ...llm import StructuredLLM
from ...trace import Tracer
from .prompts import SCENE_DIVIDER, SYSTEM

def _deterministic_issues(text: str, unit: str, min_chars: int) -> List[Issue]:
    """The cheap gate: nothing here needs a model, so it runs before anything that does."""
    stripped = text.strip()
    if not stripped:
        return [Issue("prose.empty", Severity.BLOCKING, f"{unit} came back empty", unit)]
    if len(stripped) < min_chars:
        return [Issue(
            "prose.stub", Severity.BLOCKING,
            f"{unit} is {len(stripped)} characters — a stub, not prose (minimum {min_chars})", unit)]
    return []


def _split_scenes(text: str) -> List[str]:
    """Recover the scene list from assembled markdown, so a chapter-level repair stays consistent."""
    lines = text.lstrip().split("\n")
    body = "\n".join(lines[1:]) if lines and lines[0].startswith("# ") else text
    return [part.strip() for part in body.split(f"\n{SCENE_DIVIDER}\n") if part.strip()]


def assemble_chapter(title: str, scenes: Sequence[str]) -> str:
    return f"# {title}\n\n" + f"\n\n{SCENE_DIVIDER}\n\n".join(s.strip() for s in scenes)


Verify = Callable[[str, str, List[Issue], int], Awaitable[Optional[List[Issue]]]]


async def _repair_loop(
    *,
    stage: str,
    unit: str,
    text: str,
    evaluate: Callable[[str], Awaitable[List[Issue]]],
    repair_prompt: Callable[[str, List[Issue]], str],
    llm: StructuredLLM,
    model: str,
    max_tokens: int,
    tracer: Tracer,
    max_repairs: int,
    verify: Optional[Verify] = None,
) -> Tuple[str, List[Issue], int]:
    """
    Read once → pin → repair → verify the pins, bounded. Returns the text reached and what is open.

    The unit is read in full by the gate exactly once. Its blocking issues are **pinned**, and every
    repair is then checked against that list by `verify` (the repair verifier): resolved or not, and
    did the edit break anything where it edited. The open list can therefore only shrink or be
    replaced by damage the repair demonstrably did — which is what lets a budget converge. Re-running
    the full gate instead re-rolls the question each round (calibration C7).

    `verify` returns None when the repair rewrote the unit rather than editing it; the text is then
    genuinely new and is re-read in full. Without a `verify` at all (tests, `--no-checkers`, a
    custom gate) every round is a full re-read, as before.

    Warnings from the first read are carried to the end unchanged: they never drive a repair.
    """
    issues = await evaluate(text)
    warnings = [i for i in issues if i.severity != Severity.BLOCKING]
    pinned = blocking(issues)
    repairs = 0

    while pinned and repairs < max_repairs:
        repairs += 1
        prompt = repair_prompt(text, pinned)
        # `draw=repairs`: a second repair whose prompt is byte-identical to the first (the model
        # handed the draft back unchanged, the same issues recurred) must be a *new* call, not a
        # replay of the answer that already failed — or the budget drains with no model call made.
        repaired = await llm.generate(
            prompt=prompt, system=SYSTEM, model=model, max_tokens=max_tokens, draw=repairs
        )
        tracer.record(
            f"{stage}_repair_{repairs}",
            prompt=prompt,
            system=SYSTEM,
            model=model,
            artifact=repaired,
            note=f"{len(pinned)} pinned issues",
        )

        still_open = await verify(text, repaired, pinned, repairs) if verify is not None else None
        text = repaired
        if still_open is None:
            issues = await evaluate(text)
            warnings = [i for i in issues if i.severity != Severity.BLOCKING]
            pinned = blocking(issues)
        else:
            pinned = still_open

    return text, warnings + pinned, repairs
