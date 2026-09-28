"""Agents as files (`agents/*.md`) and the map drawn from them (`storica map`)."""

import json
import re

import pytest

from storica.agent_map import build_map
from storica.agents import agent, all_agents, block, parse_agent
from storica.cli import main
from storica.llm import STAGE_MODELS


def _write_agent(root, aid, body, **meta):
    fm = {"id": aid, "name": aid.title(), "model": "sonnet", **meta}
    lines = ["---"] + [f"{k}: {json.dumps(v)}" for k, v in fm.items()] + ["---", ""]
    (root / f"{aid}.md").write_text("\n".join(lines) + body + "\n", encoding="utf-8")


def _map_data(page: str) -> dict:
    return json.loads(re.search(r'id="data">(.*?)</script>', page, re.S).group(1).replace("<\\/", "</"))


def test_every_shipped_agent_loads_with_instructions_and_a_model():
    agents = all_agents()
    assert {a.id for a in agents} == set(STAGE_MODELS)
    for a in agents:
        assert a.system.startswith("You are"), a.id
        assert a.model in ("opus", "sonnet", "haiku"), a.id
        assert a.meta.get("phase") in ("plan", "scene", "chapter", "book", "any"), a.id


def test_the_code_passes_the_file_contents_as_the_system_prompt():
    from storica.checkers import voice
    from storica.stages.prose import prompts

    assert voice.SYSTEM == agent("voice").system
    assert voice.VOICE_RUBRIC == block("voice", "rubric")
    # The writer and the micro-sense reader share one invention policy, included from _shared/.
    from storica.canon import INVENTION_POLICY

    assert INVENTION_POLICY in prompts.SYSTEM
    assert "{{include" not in prompts.SYSTEM


def test_sections_and_includes_round_trip_exactly(tmp_path):
    (tmp_path / "_shared").mkdir()
    (tmp_path / "_shared" / "policy.md").write_text("Shared rule.\n", encoding="utf-8")
    body = "You are X.\n\n{{include: policy}}\n\nEnd.\n\n<!-- rubric -->\nJudge in order:\n- one\n\n<!-- tail -->\nLast."
    _write_agent(tmp_path, "x", body)
    a = parse_agent(tmp_path / "x.md", tmp_path)
    assert a.system == "You are X.\n\nShared rule.\n\nEnd."
    assert a.blocks == {"rubric": "Judge in order:\n- one", "tail": "Last."}


def test_a_malformed_agent_file_is_refused(tmp_path):
    (tmp_path / "y.md").write_text("no frontmatter\n", encoding="utf-8")
    with pytest.raises(ValueError, match="frontmatter"):
        parse_agent(tmp_path / "y.md", tmp_path)
    _write_agent(tmp_path, "z", "body")
    (tmp_path / "z.md").rename(tmp_path / "other.md")
    with pytest.raises(ValueError, match="must match the file name"):
        parse_agent(tmp_path / "other.md", tmp_path)


def test_asking_for_a_missing_section_names_what_exists():
    with pytest.raises(KeyError, match="has: rubric"):
        block("voice", "no-such-section")


def test_map_attributes_calls_by_system_prompt_then_by_stage_pattern(tmp_path):
    agents = tmp_path / "agents"
    agents.mkdir()
    _write_agent(agents, "writer", "You are the writer.", phase="scene", trace=["_prose$"])
    trace = tmp_path / "novel" / "04_trace"
    trace.mkdir(parents=True)
    records = [
        {"seq": 1, "stage": "ch01_s1_prose", "system": "You are the writer.", "prompt": "P1", "artifact": "text"},
        {"seq": 2, "stage": "ch01_s2_prose", "system": "Older instructions.", "prompt": "P2", "artifact": "text"},
        {"seq": 3, "stage": "consensus_x", "system": None, "prompt": "", "artifact": {}},
        {"seq": 4, "stage": "mystery", "system": "Who?", "prompt": "P4", "artifact": {"a": 1}},
    ]
    for r in records:
        (trace / f"{r['seq']:03d}_{r['stage']}.json").write_text(json.dumps(r), encoding="utf-8")

    data = _map_data(build_map(tmp_path / "novel", agents))
    writer = data["calls"]["writer"]
    assert [c["seq"] for c in writer] == [1, 2]
    assert [c["current"] for c in writer] == [True, False]
    assert data["bookkeeping"] == 1 and data["unmatched"] == 1
    assert data["calls"]["_unmatched"][0]["output"] == '{\n  "a": 1\n}'


def test_map_command_writes_a_page_without_a_novel(tmp_path, capsys):
    out = tmp_path / "map.html"
    assert main(["map", "--out", str(out)]) == 0
    data = _map_data(out.read_text(encoding="utf-8"))
    assert data["novel"] is None
    assert {a["id"] for a in data["agents"]} == set(STAGE_MODELS)
    assert main(["map", str(tmp_path / "nothing-here")]) == 1
