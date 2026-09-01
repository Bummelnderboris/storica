"""
Autonomous self-adjudication (DESIGN §6.5).

When a checker escalates, the run does not stop and does not wait for a human. A fresh adjudicator
is handed the conflict, the **immutable ground truth**, and the decision log, and issues exactly
one binding ruling. Three properties make this safe to run unattended:

1. **Rulings resolve toward ground truth, never toward the mutable canon.** The brief and the
   Phase-2 canon are frozen at creation; a downstream agent may not "reconcile" a contradiction by
   inventing a bridging fact (that is precisely F11/F12).
2. **Rulings are binding and logged.** The same conflict is never re-opened — the log is consulted
   before adjudication, so escalation cannot oscillate. This is the convergence guarantee.
3. **Amending canon is structurally constrained.** An `amend_canon` ruling must quote the clause of
   ground truth that the canon violates. No quoted clause, no amendment — enforced in code, not
   asked for politely.

On repeated failure to produce a permissible ruling the unit is quarantined by the caller rather
than shipped: bounded, visible, and excluded from the finished novel.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from .brief import Brief, load_brief
from .canon import StoryModel, canon_slice
from .llm import StructuredLLM, stage_model
from .reports import DecisionLog, DecisionRecord, Ruling, RulingKind
from .trace import Tracer

PathLike = Union[str, Path]

SYSTEM = """You are the Adjudicator of an autonomous novel pipeline.

A conflict has been escalated because it cannot be fixed locally. You issue exactly ONE binding
ruling. It is permanent: the same conflict will never be re-opened, so rule for good.

Your authority, in order of preference:
- 'correct_the_unit' — the usual ruling. The unit is wrong and canon is right; say precisely how
  the unit must change.
- 'spawn_specialist' — the conflict needs bounded work by a fresh agent (e.g. an underspecified
  timeline). Emit the sub-task and the instructions that agent is to be given.
- 'amend_canon' — permitted ONLY when the CANON ITSELF violates the immutable ground truth below.
  You must quote the ground-truth clause it violates. The ground truth itself can never be amended.

You may NOT invent a fact to bridge the contradiction. If two things cannot both be true, one of
them is wrong — say which, and why, from the ground truth. Prior rulings in the decision log are
binding context: never contradict or re-litigate them."""


class AdjudicationFailed(RuntimeError):
    """The adjudicator could not produce a permissible ruling within its attempt budget."""

    def __init__(self, unit: str, conflict: str, reason: str):
        self.unit = unit
        self.conflict = conflict
        self.reason = reason
        super().__init__(f"adjudication failed for {unit}: {reason}")


@dataclass
class GroundTruth:
    """
    What may never be edited: the creator's brief, and the canon as locked at creation.

    The locked canon is version 1 in `01_canon/history/` — the world and cast as stage 2 committed
    them, before any prose existed to reinterpret them.
    """

    brief: Brief
    locked_canon: StoryModel

    @classmethod
    def load(cls, novel_dir: PathLike, *, locked_version: int = 1) -> "GroundTruth":
        novel_dir = Path(novel_dir)
        snapshot = novel_dir / "01_canon" / "history" / f"v{locked_version:04d}.json"
        if not snapshot.exists():
            raise FileNotFoundError(
                f"no locked canon at {snapshot} — ground truth is established when stage 2 commits"
            )
        return cls(
            brief=load_brief(novel_dir / "00_input"),
            locked_canon=StoryModel.model_validate_json(snapshot.read_text(encoding="utf-8")),
        )

    def prompt_block(self) -> str:
        return f"""# IMMUTABLE GROUND TRUTH (may never be amended — resolve toward this)

{self.brief.prompt_block()}

## Canon as locked at creation
{canon_slice(self.locked_canon)}"""


def permissible(ruling: Ruling) -> Optional[str]:
    """Return why a ruling is impermissible, or None if it stands."""
    if ruling.kind == RulingKind.AMEND_CANON:
        if not ruling.ground_truth_violation.strip():
            return (
                "an 'amend_canon' ruling must quote the clause of the immutable ground truth that "
                "the canon violates; you quoted none, so canon stands and the unit must change"
            )
        if not ruling.canon_amendment.strip():
            return "an 'amend_canon' ruling must state exactly what changes in canon"
    if ruling.kind == RulingKind.SPAWN_SPECIALIST and not ruling.specialist_task.strip():
        return "a 'spawn_specialist' ruling must state the sub-task and the instructions"
    if not ruling.instruction.strip():
        return "every ruling must state what the downstream agent is to do"
    if not ruling.binding_summary.strip():
        return "every ruling must state, in one line, what is now settled"
    return None


class Adjudicator:
    """Issues binding rulings on escalated conflicts."""

    def __init__(
        self,
        llm: StructuredLLM,
        *,
        ground_truth: GroundTruth,
        log: DecisionLog,
        model: str = stage_model("adjudicator"),
        tracer: Optional[Tracer] = None,
        max_attempts: int = 2,
    ):
        self.llm = llm
        self.ground_truth = ground_truth
        self.log = log
        self.model = model
        self.tracer = tracer or Tracer(None)
        self.max_attempts = max_attempts

    async def rule(self, *, unit: str, conflict: str, context: str = "") -> DecisionRecord:
        """
        Settle a conflict. If it was settled before, the earlier ruling is returned unchanged and
        no model is called — that is what makes escalation converge instead of oscillate.
        """
        existing = self.log.find(unit, conflict)
        if existing is not None:
            return existing

        correction = ""
        for attempt in range(1, self.max_attempts + 1):
            prompt = self._prompt(unit=unit, conflict=conflict, context=context, correction=correction)
            ruling = await self.llm.parse(
                prompt=prompt, schema=Ruling, system=SYSTEM, model=self.model, max_tokens=8000
            )
            self.tracer.record(
                f"adjudication_{unit}",
                prompt=prompt,
                system=SYSTEM,
                model=self.model,
                artifact=ruling,
                note=f"attempt {attempt}: {ruling.kind.value}",
            )
            problem = permissible(ruling)
            if problem is None:
                return self.log.append(unit, conflict, ruling)
            correction = problem

        raise AdjudicationFailed(unit, conflict, correction)

    def _prompt(self, *, unit: str, conflict: str, context: str, correction: str) -> str:
        retry = (
            f"\n## Your previous ruling was not permissible\n{correction}\nRule again, within your "
            "authority.\n"
            if correction
            else ""
        )
        return f"""{self.ground_truth.prompt_block()}

{self.log.as_prompt_block()}

# The escalated conflict
- unit: {unit}
- conflict: {conflict}

{f"## Context{chr(10)}{context}" if context else ""}
{retry}
## Task
Issue exactly one binding ruling that settles this conflict for the rest of the run."""
