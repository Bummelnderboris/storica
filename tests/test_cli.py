"""
The command line — the whole user interface, and until now the only untested module.

What matters here is not argument parsing for its own sake but the three contracts a driving loop
and a human both depend on:

- **exit codes are the API.** 0 done, 1 refused, 2 needs an answer, 3 the answer written was wrong.
  `/write-novel` branches on these without parsing text, so a changed code silently breaks it.
- **the brief is written once.** `new` on an existing novel must refuse rather than overwrite; the
  brief is ground truth and everything downstream resolves toward it.
- **status reads the disk.** It must work at every stage of a run, including before one has started,
  because it is what a person types when they have lost track.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from storica.cli import build_parser, main

AUTHORS_ROOT = Path(__file__).resolve().parents[1] / "authors"


def _new(tmp_path: Path, **over) -> int:
    argv = ["new", str(tmp_path / "book"), "--author", over.pop("author", "duerrenmatt")]
    for k, v in over.items():
        argv += [f"--{k}", str(v)]
    return main(argv)


# --------------------------------------------------------------------------------------------
# new
# --------------------------------------------------------------------------------------------

def test_new_creates_the_skeleton_and_the_brief(tmp_path):
    assert _new(tmp_path, spark="A judge re-tries his own case.", language="de", chapters=6) == 0

    book = tmp_path / "book"
    for sub in ("00_input", "01_canon", "02_plan/chapters", "03_drafts", "04_trace", "05_reports"):
        assert (book / sub).is_dir(), f"missing {sub}"

    brief = (book / "00_input" / "brief.yaml").read_text(encoding="utf-8")
    assert "author_id: duerrenmatt" in brief
    assert "A judge re-tries his own case." in brief
    assert "language: de" in brief


def test_new_refuses_to_overwrite_an_existing_brief(tmp_path, capsys):
    assert _new(tmp_path) == 0
    assert _new(tmp_path) == 1, "the brief is immutable ground truth; a second new must refuse"
    assert "immutable" in capsys.readouterr().out


def test_new_requires_an_author(tmp_path):
    with pytest.raises(SystemExit):
        main(["new", str(tmp_path / "book")])


# --------------------------------------------------------------------------------------------
# status — must work at every stage, including before there is anything
# --------------------------------------------------------------------------------------------

def test_status_on_a_novel_that_has_not_started(tmp_path, capsys):
    _new(tmp_path)
    assert main(["status", str(tmp_path / "book")]) == 0
    assert "not established yet" in capsys.readouterr().out


def test_status_reports_quarantine_and_cost_from_the_last_run(tmp_path, capsys):
    _new(tmp_path)
    book = tmp_path / "book"
    (book / "05_reports").mkdir(parents=True, exist_ok=True)
    (book / "05_reports" / "quarantine.jsonl").write_text(
        json.dumps({"unit": "ch01", "reason": "budget exhausted", "issues": [], "at": "now"}) + "\n",
        encoding="utf-8",
    )
    (book / "05_reports" / "run_report.json").write_text(
        json.dumps({"usage": {"calls": 42, "estimated_cost_usd": 3.5}}), encoding="utf-8"
    )

    assert main(["status", str(book)]) == 0
    out = capsys.readouterr().out
    assert "QUARANTINED: ch01" in out, "a dropped chapter must be loud"
    assert "42 calls" in out and "$3.50" in out


# --------------------------------------------------------------------------------------------
# run — the exit codes a driving loop branches on
# --------------------------------------------------------------------------------------------

def test_run_returns_2_and_writes_a_request_when_it_needs_an_answer(tmp_path, capsys):
    _new(tmp_path, spark="A judge re-tries his own case.")
    book = tmp_path / "book"

    code = main(["run", str(book), "--driver", "replay", "--authors", str(AUTHORS_ROOT)])
    assert code == 2, "an unanswered call is a pause, not a failure"

    out = capsys.readouterr().out
    assert "[paused]" in out
    requests = list((book / "06_session" / "requests").glob("*.request.md"))
    assert len(requests) == 1
    assert "## System prompt" in requests[0].read_text(encoding="utf-8")


def test_run_returns_3_when_a_recorded_answer_does_not_fit_its_schema(tmp_path, capsys):
    _new(tmp_path, spark="A judge re-tries his own case.")
    book = tmp_path / "book"
    main(["run", str(book), "--driver", "replay", "--authors", str(AUTHORS_ROOT)])

    key = next((book / "06_session" / "requests").glob("*.request.md")).name.split(".")[0]
    (book / "06_session" / "responses" / f"{key}.response.json").write_text(
        '{"wrong": "shape"}', encoding="utf-8"
    )

    code = main(["run", str(book), "--driver", "replay", "--authors", str(AUTHORS_ROOT)])
    assert code == 3, "a malformed answer must be distinguishable from a missing one"
    assert "[malformed]" in capsys.readouterr().out


def test_run_without_an_api_key_says_so_instead_of_crashing(tmp_path, monkeypatch):
    monkeypatch.setattr("storica.cli._load_dotenv", lambda: None)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    _new(tmp_path)

    with pytest.raises(SystemExit) as exit_info:
        main(["run", str(tmp_path / "book"), "--driver", "anthropic"])
    assert "ANTHROPIC_API_KEY" in str(exit_info.value)


# --------------------------------------------------------------------------------------------
# the flags that cost money
# --------------------------------------------------------------------------------------------

def test_the_defaults_that_decide_what_a_run_costs():
    args = build_parser().parse_args(["run", "somewhere"])
    assert args.driver == "replay", "the default must not spend money by accident"
    assert args.prose_candidates == 3
    assert args.checker_samples == 3
    assert args.max_repairs == 2
    assert args.no_audit is False and args.no_checkers is False


def test_the_cheap_configuration_parses():
    args = build_parser().parse_args(
        ["run", "somewhere", "--prose-candidates", "1", "--checker-samples", "1", "--no-audit"]
    )
    assert (args.prose_candidates, args.checker_samples, args.no_audit) == (1, 1, True)


def test_a_command_is_required():
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


# --------------------------------------------------------------------------------------------
# cost accounting
# --------------------------------------------------------------------------------------------

def test_usage_prices_each_tier_and_totals_the_run():
    from storica.llm import PRICES, Usage

    u = Usage()
    u.record(model="opus", input_tokens=1_000_000, output_tokens=1_000_000)
    u.record(model="sonnet", input_tokens=1_000_000, output_tokens=1_000_000)

    assert u.calls == 2
    assert u.cost_usd == pytest.approx(sum(PRICES["opus"]) + sum(PRICES["sonnet"]))
    assert u.as_dict()["calls_by_model"] == {"opus": 1, "sonnet": 1}
    assert "2 calls" in u.summary()


def test_an_unknown_model_is_counted_but_not_priced():
    """A model we have no rate for must not silently invent one."""
    from storica.llm import Usage

    u = Usage()
    u.record(model="something-new", input_tokens=1_000, output_tokens=1_000)
    assert u.calls == 1 and u.input_tokens == 1_000
    assert u.cost_usd == 0.0


def test_an_empty_env_assignment_is_not_loaded_as_a_credential(tmp_path, monkeypatch):
    """
    `.env.example` is copied with `ANTHROPIC_API_KEY=`. Exporting that as "" would shadow a key
    supplied another way and produce an auth error pointing at the wrong cause.
    """
    from storica import cli

    env = tmp_path / ".env"
    env.write_text("ANTHROPIC_API_KEY=\nSOMETHING_REAL=value\n", encoding="utf-8")
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("SOMETHING_REAL", raising=False)

    cli._load_dotenv()

    import os
    assert "ANTHROPIC_API_KEY" not in os.environ, "an empty assignment must not be exported"
    assert os.environ["SOMETHING_REAL"] == "value", "real values must still load"
