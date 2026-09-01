"""
Tests for the replay driver — running the pipeline with no API key.

Run from the backend/ directory:
    .venv/bin/python -m pytest tests/ -q

The behaviour that matters: a call with no recorded answer pauses the run with a readable request
instead of blocking or failing, and a call that has been answered replays instantly. That is what
makes an agent-driven end-to-end run resumable.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from pydantic import BaseModel, ConfigDict

from storica.checkers.base import Verdict
from storica.drivers import MalformedResponse, ReplayLLM, ResponseNeeded


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str


def _parse(llm: ReplayLLM, prompt: str = "what is the premise?", **over):
    return asyncio.run(llm.parse(prompt=prompt, schema=Answer, system="be terse", **over))


def _generate(llm: ReplayLLM, prompt: str = "write the scene", **over):
    return asyncio.run(llm.generate(prompt=prompt, system="be terse", **over))


# --------------------------------------------------------------------------------------------
# Pausing
# --------------------------------------------------------------------------------------------

def test_unanswered_call_writes_a_readable_request_and_pauses(tmp_path):
    llm = ReplayLLM(tmp_path, stage_hint="conception")

    with pytest.raises(ResponseNeeded) as exc:
        _parse(llm)

    request = exc.value.request_path.read_text()
    assert "what is the premise?" in request          # the real prompt, not a summary
    assert "be terse" in request                       # and the real system prompt
    assert "Required response schema (`Answer`)" in request
    assert '"additionalProperties": false' in request  # the schema to answer against
    assert exc.value.response_path.suffix == ".json"
    assert llm.requested == 1 and llm.replayed == 0


def test_prose_call_asks_for_markdown_not_json(tmp_path):
    llm = ReplayLLM(tmp_path)

    with pytest.raises(ResponseNeeded) as exc:
        _generate(llm)

    assert exc.value.is_text and exc.value.response_path.suffix == ".md"
    assert "Write the prose" in exc.value.request_path.read_text()


# --------------------------------------------------------------------------------------------
# Replay
# --------------------------------------------------------------------------------------------

def test_an_answered_call_replays_without_pausing(tmp_path):
    llm = ReplayLLM(tmp_path)
    with pytest.raises(ResponseNeeded) as exc:
        _parse(llm)
    exc.value.response_path.write_text(json.dumps({"value": "the premise"}))

    # a fresh driver, as if the runner were started again
    again = ReplayLLM(tmp_path)
    assert _parse(again).value == "the premise"
    assert again.replayed == 1 and again.requested == 0


def test_prose_replays_verbatim(tmp_path):
    llm = ReplayLLM(tmp_path)
    with pytest.raises(ResponseNeeded) as exc:
        _generate(llm)
    exc.value.response_path.write_text("Der Amtsarzt unterschrieb.\n")

    assert _generate(ReplayLLM(tmp_path)) == "Der Amtsarzt unterschrieb.\n"


def test_a_malformed_answer_names_the_file_to_fix(tmp_path):
    """
    The schema is enforced on replay exactly as on the API — but a driven run answers hundreds of
    calls, so the error has to say *which* answer is wrong or it is useless.
    """
    llm = ReplayLLM(tmp_path)
    with pytest.raises(ResponseNeeded) as exc:
        _parse(llm)
    exc.value.response_path.write_text(json.dumps({"wrong_field": 1}))

    with pytest.raises(MalformedResponse) as bad:
        _parse(ReplayLLM(tmp_path))

    assert bad.value.response_path == exc.value.response_path
    assert bad.value.schema_name == "Answer"
    assert "fix the file" in str(bad.value)


# --------------------------------------------------------------------------------------------
# Keying
# --------------------------------------------------------------------------------------------

def test_the_key_is_content_addressed(tmp_path):
    """A changed prompt asks a new question; an unchanged one replays."""
    llm = ReplayLLM(tmp_path)
    with pytest.raises(ResponseNeeded) as first:
        _parse(llm, prompt="prompt A")
    first.value.response_path.write_text(json.dumps({"value": "A"}))

    assert _parse(ReplayLLM(tmp_path), prompt="prompt A").value == "A"

    with pytest.raises(ResponseNeeded) as second:
        _parse(ReplayLLM(tmp_path), prompt="prompt B")
    assert second.value.key != first.value.key


def test_the_model_alias_is_part_of_the_key(tmp_path):
    llm = ReplayLLM(tmp_path)
    with pytest.raises(ResponseNeeded) as opus:
        _parse(llm, model="opus")
    with pytest.raises(ResponseNeeded) as sonnet:
        _parse(llm, model="sonnet")
    assert opus.value.key != sonnet.value.key


# --------------------------------------------------------------------------------------------
# Introspection
# --------------------------------------------------------------------------------------------

def test_pending_lists_only_unanswered_requests(tmp_path):
    llm = ReplayLLM(tmp_path)
    with pytest.raises(ResponseNeeded) as a:
        _parse(llm, prompt="A")
    with pytest.raises(ResponseNeeded):
        _parse(llm, prompt="B")

    assert len(llm.pending()) == 2
    a.value.response_path.write_text(json.dumps({"value": "answered"}))
    assert len(llm.pending()) == 1


# --------------------------------------------------------------------------------------------
# Repeated draws of one prompt (generate-and-select)
# --------------------------------------------------------------------------------------------

def test_identical_prose_prompts_get_separate_slots(tmp_path):
    """
    Generate-and-select draws k candidates from the SAME prompt on purpose. Content addressing alone
    would hand back k copies of one cached answer and the selector would choose between identical
    drafts — selection silently becomes a no-op under replay.
    """
    llm = ReplayLLM(tmp_path)
    keys = []
    for i in range(3):
        try:
            asyncio.run(llm.generate(prompt="same prompt", model="opus", draw=i + 1))
        except ResponseNeeded as need:
            keys.append(need.key)
    assert len(set(keys)) == 3, "three draws of one prompt must be three distinct requests"


def test_repeated_draws_replay_in_the_same_order_after_a_restart(tmp_path):
    """Resumability: draw 2 must still resolve to draw 2 on the next process."""
    llm = ReplayLLM(tmp_path)
    keys = []
    for i in range(2):
        try:
            asyncio.run(llm.generate(prompt="same prompt", model="opus", draw=i + 1))
        except ResponseNeeded as need:
            keys.append(need.key)
            (tmp_path / "responses" / f"{need.key}.response.md").write_text(
                f"draft for {need.key}", encoding="utf-8"
            )

    fresh = ReplayLLM(tmp_path)
    got = [asyncio.run(fresh.generate(prompt="same prompt", model="opus", draw=i + 1)) for i in range(2)]
    assert got == [f"draft for {keys[0]}", f"draft for {keys[1]}"]

    # And out of order — the point of an explicit index is that completion order cannot decide a slot.
    shuffled = ReplayLLM(tmp_path)
    assert asyncio.run(shuffled.generate(prompt="same prompt", model="opus", draw=2)) == f"draft for {keys[1]}"
    assert asyncio.run(shuffled.generate(prompt="same prompt", model="opus", draw=1)) == f"draft for {keys[0]}"


def test_repeated_parse_draws_get_their_own_slots(tmp_path):
    """
    Consensus sampling draws one checker k times from an identical prompt and blocks on a majority.

    Keyed on content alone, all k collapse onto one cached answer and majority-of-3 becomes one
    verdict counted three times — the gate looks sampled and is not. This is the same failure that
    made generate-and-select a no-op (de44dc2); it applies to `parse` for exactly the same reason.
    """
    llm = ReplayLLM(tmp_path)
    keys = []
    for i in range(3):
        try:
            asyncio.run(llm.parse(prompt="judge this", schema=Verdict, model="sonnet", draw=i + 1))
        except ResponseNeeded as need:
            keys.append(need.key)
            (tmp_path / "responses" / f"{need.key}.response.json").write_text(
                json.dumps({"decision": "pass", "summary": f"draw {i}", "issues": [], "conflict": ""}),
                encoding="utf-8",
            )

    assert len(set(keys)) == 3, "three draws of one prompt must not share a cache slot"

    fresh = ReplayLLM(tmp_path)
    got = [asyncio.run(fresh.parse(prompt="judge this", schema=Verdict, model="sonnet", draw=i + 1))
           for i in range(3)]
    assert [v.summary for v in got] == ["draw 0", "draw 1", "draw 2"]
    assert fresh.requested == 0, "a resumed run must replay every draw, not ask again"


def test_different_prompts_are_unaffected(tmp_path):
    """The suffix must only apply to verbatim repeats, not to ordinary distinct calls."""
    llm = ReplayLLM(tmp_path)
    first = second = None
    try:
        asyncio.run(llm.generate(prompt="prompt A", model="opus"))
    except ResponseNeeded as need:
        first = need.key
    try:
        asyncio.run(llm.generate(prompt="prompt B", model="opus"))
    except ResponseNeeded as need:
        second = need.key
    assert first != second
    assert "-" not in first and "-" not in second
