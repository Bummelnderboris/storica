"""
Run trace (`novels/<slug>/04_trace/`).

Autonomy is made auditable by writing *everything* down (DESIGN §6.5): every filled prompt and
every artifact, so a run nobody watched can still be reconstructed after the fact. Deliberately
dumb — append-only JSON files, no index, no DB.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Optional, Union

from pydantic import BaseModel

PathLike = Union[str, Path]


class Tracer:
    """
    Writes `NNN_<stage>.json` per agent call into a trace directory.

    Records are **deduplicated by content**. A resumable run re-executes every completed stage on
    each restart (replaying its recorded answers), and a replay-driven run restarts once per
    unanswered call — so without this the trace would accumulate a fresh copy of every earlier call
    on every resume, and the audit trail would say a chapter was written nine times when it was
    written once.
    """

    def __init__(self, trace_dir: Optional[PathLike]):
        self.trace_dir = Path(trace_dir) if trace_dir is not None else None
        self._seq = 0
        self._digests: set[str] = set()
        if self.trace_dir is not None:
            self.trace_dir.mkdir(parents=True, exist_ok=True)
            existing = sorted(self.trace_dir.glob("*.json"))
            self._seq = len(existing)
            for path in existing:
                try:
                    self._digests.add(json.loads(path.read_text(encoding="utf-8"))["digest"])
                except (json.JSONDecodeError, KeyError, OSError):
                    continue  # a hand-edited or pre-dedup record simply does not suppress anything

    def record(
        self,
        stage: str,
        *,
        prompt: str,
        system: Optional[str] = None,
        model: str = "",
        artifact: Any = None,
        note: str = "",
    ) -> Optional[Path]:
        """
        Persist one agent call.

        No-op when the tracer has no directory (unit tests), and no-op when an identical record is
        already on disk — see the note on deduplication above.
        """
        if self.trace_dir is None:
            return None

        body = {
            "stage": stage,
            "model": model,
            "note": note,
            "system": system,
            "prompt": prompt,
            "artifact": artifact.model_dump(mode="json") if isinstance(artifact, BaseModel) else artifact,
        }
        digest = hashlib.sha256(
            json.dumps(body, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
        ).hexdigest()[:16]
        if digest in self._digests:
            return None
        self._digests.add(digest)

        self._seq += 1
        payload = {"seq": self._seq, "digest": digest, **body}
        path = self.trace_dir / f"{self._seq:03d}_{stage}.json"
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return path
