"""
The generate → check → repair loop shared by every stage (DESIGN §6).

One place owns the shape so every seam behaves identically: generate a unit, evaluate it with the
cheap deterministic checker and then (only if that passes) the expensive LLM checker, and on any
blocking issue hand the issue list plus the current draft back for a **grounded** repair — the
repair agent is told exactly what is broken, so it fixes rather than reimagines.

Two properties make this safe to run unattended: the budget is bounded (`max_repairs`), and a
still-blocking unit raises instead of being passed downstream.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable, List, Optional, Type, TypeVar

from pydantic import BaseModel

from ..canon import Issue, blocking
from ..llm import StructuredLLM
from ..trace import Tracer

T = TypeVar("T", bound=BaseModel)


class GateFailed(RuntimeError):
    """A unit still had blocking issues when the repair budget ran out."""

    def __init__(self, issues: List[Issue]):
        self.issues = issues
        super().__init__("gate failed:\n" + "\n".join(f"  {i}" for i in issues))


@dataclass
class GateOutcome:
    draft: BaseModel
    issues: List[Issue] = field(default_factory=list)
    repairs: int = 0

    @property
    def is_valid(self) -> bool:
        return not blocking(self.issues)


async def run_gated(
    *,
    llm: StructuredLLM,
    schema: Type[T],
    system: str,
    prompt: str,
    repair_prompt: Callable[[T, List[Issue]], str],
    evaluate: Callable[[T], Awaitable[List[Issue]]],
    stage: str,
    model: str = "sonnet",
    max_tokens: int = 16000,
    tracer: Optional[Tracer] = None,
    max_repairs: int = 2,
    strict: bool = True,
    failure: Type[GateFailed] = GateFailed,
) -> GateOutcome:
    """
    Generate a `schema` unit and repair it until `evaluate` reports no blocking issues.

    `evaluate` returns *all* issues (warnings included) — only blocking ones drive repair, so a
    warning can never spin the loop.
    """
    tracer = tracer or Tracer(None)

    draft = await llm.parse(
        prompt=prompt, schema=schema, system=system, model=model, max_tokens=max_tokens
    )
    tracer.record(stage, prompt=prompt, system=system, model=model, artifact=draft)

    issues = await evaluate(draft)
    repairs = 0

    while blocking(issues) and repairs < max_repairs:
        repairs += 1
        rprompt = repair_prompt(draft, blocking(issues))
        draft = await llm.parse(
            prompt=rprompt, schema=schema, system=system, model=model, max_tokens=max_tokens
        )
        tracer.record(
            f"{stage}_repair_{repairs}",
            prompt=rprompt,
            system=system,
            model=model,
            artifact=draft,
            note=f"{len(blocking(issues))} blocking issues",
        )
        issues = await evaluate(draft)

    outcome = GateOutcome(draft=draft, issues=issues, repairs=repairs)
    if strict and not outcome.is_valid:
        raise failure(blocking(issues))
    return outcome


def format_issues(issues: List[Issue]) -> str:
    return "\n".join(f"- {i}" for i in issues)
