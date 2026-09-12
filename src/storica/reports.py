"""
Run reports (`novels/<slug>/05_reports/`) — the record that makes unattended operation auditable.

Three artifacts, all append-only:

- `decisions.jsonl` — every binding ruling. **This file is what guarantees convergence** (DESIGN
  §6.5): a conflict that has been ruled on is never re-opened, so escalation cannot oscillate. The
  log is consulted *before* adjudication, not just written after it.
- `quarantine.jsonl` — units that exhausted their repair budget. They are excluded from `novel.md`
  rather than shipped broken, and they are loud on disk so a human can see exactly what was dropped.
- `run_report.json` — the summary of a run.

Nothing here is ever rewritten in place. The point of the trace is that it records what actually
happened, including the parts that went badly.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

PathLike = Union[str, Path]

DECISIONS_FILE = "decisions.jsonl"
QUARANTINE_FILE = "quarantine.jsonl"
RUN_REPORT_FILE = "run_report.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def conflict_key(unit: str, conflict: str) -> str:
    """
    Stable identity for a conflict.

    Normalised so that the same conflict phrased with different whitespace or casing is recognised
    as already-ruled. This is deliberately conservative: a near-identical rewording will produce a
    different key and be adjudicated again, which is wasteful but safe. Collapsing genuinely
    different conflicts into one ruling would not be.
    """
    normalised = " ".join(f"{unit}|{conflict}".lower().split())
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()[:16]


class RulingKind(str, Enum):
    CORRECT_UNIT = "correct_the_unit"      # the usual case: the unit is wrong, canon is right
    AMEND_CANON = "amend_canon"            # only when canon violates immutable ground truth
    SPAWN_SPECIALIST = "spawn_specialist"  # emit a sub-task with generated instructions


class Ruling(BaseModel):
    """One adjudication. Exactly one of these settles a conflict, permanently."""

    model_config = ConfigDict(extra="forbid")

    kind: RulingKind
    reasoning: str = Field(description="Why this ruling follows from the immutable ground truth.")
    instruction: str = Field(description="What the downstream agent must now do. Concrete and bounded.")
    canon_amendment: str = Field(
        description="Only for amend_canon: exactly what changes in canon. Empty otherwise."
    )
    ground_truth_violation: str = Field(
        description="Only for amend_canon: the specific clause of the immutable ground truth that "
        "the CANON violates, quoted. An amendment without one is not permitted. Empty otherwise."
    )
    specialist_task: str = Field(
        description="Only for spawn_specialist: the sub-task and the instructions the fresh agent "
        "is to be given. Empty otherwise."
    )
    binding_summary: str = Field(description="One line stating what is now settled and may never be re-opened.")


class DecisionRecord(BaseModel):
    """A ruling as stored: the conflict it settles, plus its identity."""

    model_config = ConfigDict(extra="forbid")

    key: str
    unit: str
    conflict: str
    ruling: Ruling
    at: str


class QuarantineRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit: str
    reason: str
    issues: List[str]
    at: str
    released: bool = False  # a later record that lifts the quarantine (`--retry-quarantined`)


class DecisionLog:
    """
    Append-only log of binding rulings, backed by `decisions.jsonl`.

    `find` is the convergence mechanism: an adjudicator consults it first and, on a hit, is bound
    by the earlier ruling instead of forming a new opinion.
    """

    def __init__(self, reports_dir: Optional[PathLike]):
        self.reports_dir = Path(reports_dir) if reports_dir is not None else None
        self._memory: List[DecisionRecord] = []
        if self.reports_dir is not None:
            self.reports_dir.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Optional[Path]:
        return self.reports_dir / DECISIONS_FILE if self.reports_dir else None

    def records(self) -> List[DecisionRecord]:
        if self.path is None or not self.path.exists():
            return list(self._memory)
        return [
            DecisionRecord.model_validate_json(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def find(self, unit: str, conflict: str) -> Optional[DecisionRecord]:
        """The binding ruling for this conflict, if one was already made."""
        key = conflict_key(unit, conflict)
        return next((r for r in self.records() if r.key == key), None)

    def append(self, unit: str, conflict: str, ruling: Ruling, at: Optional[str] = None) -> DecisionRecord:
        record = DecisionRecord(
            key=conflict_key(unit, conflict),
            unit=unit,
            conflict=conflict,
            ruling=ruling,
            at=at or _now(),
        )
        if self.path is None:
            self._memory.append(record)
        else:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(record.model_dump_json() + "\n")
        return record

    def as_prompt_block(self, limit: int = 20) -> str:
        """The decision log as an adjudicator sees it — prior rulings are binding context."""
        records = self.records()[-limit:]
        if not records:
            return "# Prior binding rulings\n(none yet)"
        lines = "\n".join(
            f"- [{r.key}] {r.unit}: {r.conflict}\n    -> {r.ruling.kind.value}: {r.ruling.binding_summary}"
            for r in records
        )
        return f"# Prior binding rulings (BINDING — never contradict or re-open these)\n{lines}"


class QuarantineLog:
    """
    Units excluded from the finished novel because they could not be made correct.

    A quarantine can be *released* — appended, never deleted — so a person can raise the repair
    budget and try the unit again without losing the record of why it was dropped the first time.
    A unit is quarantined iff its most recent record is not a release.
    """

    def __init__(self, reports_dir: Optional[PathLike]):
        self.reports_dir = Path(reports_dir) if reports_dir is not None else None
        self._memory: List[QuarantineRecord] = []
        if self.reports_dir is not None:
            self.reports_dir.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Optional[Path]:
        return self.reports_dir / QUARANTINE_FILE if self.reports_dir else None

    def records(self) -> List[QuarantineRecord]:
        if self.path is None or not self.path.exists():
            return list(self._memory)
        return [
            QuarantineRecord.model_validate_json(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def add(self, unit: str, reason: str, issues: List[str], at: Optional[str] = None) -> QuarantineRecord:
        record = QuarantineRecord(unit=unit, reason=reason, issues=issues, at=at or _now())
        if self.path is None:
            self._memory.append(record)
        else:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(record.model_dump_json() + "\n")
        return record

    def release(self, unit: str, reason: str, at: Optional[str] = None) -> QuarantineRecord:
        """Lift a quarantine so the next run re-attempts the unit. Appended, like everything here."""
        record = QuarantineRecord(unit=unit, reason=reason, issues=[], at=at or _now(), released=True)
        if self.path is None:
            self._memory.append(record)
        else:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(record.model_dump_json() + "\n")
        return record

    def units(self) -> List[str]:
        """Units currently quarantined, in first-quarantined order."""
        latest: Dict[str, bool] = {}
        for r in self.records():
            latest[r.unit] = r.released
        return [unit for unit, released in latest.items() if not released]

    def is_quarantined(self, unit: str) -> bool:
        return unit in set(self.units())


def write_run_report(reports_dir: PathLike, payload: Dict[str, Any]) -> Path:
    """Write the run summary. Overwritten per run by design — the jsonl logs are the history."""
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / RUN_REPORT_FILE
    # Atomic: `status` reads this file, and a run killed mid-write must not leave half a JSON.
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"at": _now(), **payload}, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)
    return path
