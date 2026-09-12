"""
Tests for the run trace.

Run from the repo root:
    .venv/bin/python -m pytest tests/ -q

The trace is the evidence that an unattended run can be reconstructed afterwards, so the thing
worth testing is that it stays *truthful* across resumes: a resumable pipeline re-executes every
completed stage on restart, and a replay-driven run restarts once per unanswered call. Without
content deduplication the trace would claim a chapter was written nine times when it was written
once — which is worse than no trace, because it reads as evidence.
"""

from __future__ import annotations

import json

from pydantic import BaseModel

from storica.trace import Tracer


class Artifact(BaseModel):
    value: str


def _records(tmp_path):
    return sorted(p.name for p in tmp_path.glob("*.json"))


def test_records_a_call_with_prompt_and_artifact(tmp_path):
    Tracer(tmp_path).record("world_cast", prompt="p", system="s", model="sonnet",
                            artifact=Artifact(value="x"), note="n")

    payload = json.loads((tmp_path / "001_world_cast.json").read_text())
    assert payload["prompt"] == "p" and payload["artifact"] == {"value": "x"}
    assert payload["seq"] == 1 and payload["digest"]


def test_an_identical_call_is_not_recorded_twice(tmp_path):
    """The resume case: the same stage runs again with a replayed answer."""
    for _ in range(3):
        Tracer(tmp_path).record("prose", prompt="p", model="opus", artifact="text")

    assert _records(tmp_path) == ["001_prose.json"]


def test_a_genuinely_different_call_is_recorded(tmp_path):
    tracer = Tracer(tmp_path)
    tracer.record("prose", prompt="scene one", model="opus", artifact="a")
    tracer.record("prose", prompt="scene two", model="opus", artifact="b")

    assert _records(tmp_path) == ["001_prose.json", "002_prose.json"]


def test_a_repair_of_the_same_stage_is_kept(tmp_path):
    """Dedup must not swallow a real second attempt — same stage, different artifact."""
    tracer = Tracer(tmp_path)
    tracer.record("ch01_prose", prompt="p", model="opus", artifact="first attempt")
    tracer.record("ch01_prose", prompt="p", model="opus", artifact="repaired")

    assert len(_records(tmp_path)) == 2


def test_dedup_survives_a_new_tracer_over_an_existing_directory(tmp_path):
    Tracer(tmp_path).record("arc", prompt="p", model="sonnet", artifact="a")
    Tracer(tmp_path).record("arc", prompt="p", model="sonnet", artifact="a")
    Tracer(tmp_path).record("arc", prompt="p2", model="sonnet", artifact="b")

    assert _records(tmp_path) == ["001_arc.json", "002_arc.json"]


def test_a_tracer_without_a_directory_is_a_no_op():
    assert Tracer(None).record("stage", prompt="p", artifact="a") is None


def test_enum_carrying_artifacts_serialise(tmp_path):
    """Verdicts and rulings carry enums; a trace that cannot serialise them records nothing."""
    from storica.checkers import Decision, Verdict

    Tracer(tmp_path).record(
        "check", prompt="p", model="sonnet",
        artifact=Verdict(decision=Decision.PASS, summary="ok", issues=[], conflict=""),
    )
    payload = json.loads((tmp_path / "001_check.json").read_text())
    assert payload["artifact"]["decision"] == "pass"
