"""
Tests for P5's escalation machinery: the decision log, quarantine, and the adjudicator.

Run from the backend/ directory:
    venv/bin/python -m pytest app/v2/tests/ -q

The properties under test are the ones that make unattended operation safe (DESIGN §6.5):
rulings resolve toward immutable ground truth, they are binding and never re-litigated, canon may
only be amended against a quoted ground-truth clause, and a unit that cannot be settled is
quarantined rather than shipped.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from app.v2.adjudicator import AdjudicationFailed, Adjudicator, GroundTruth, permissible
from app.v2.brief import Brief, save_brief
from app.v2.canon import (
    Character,
    CharacterRole,
    Constraints,
    Premise,
    StoryModel,
    save_canon,
)
from app.v2.llm import FakeStructuredLLM
from app.v2.reports import (
    DecisionLog,
    QuarantineLog,
    Ruling,
    RulingKind,
    conflict_key,
    write_run_report,
)

REPO_ROOT = Path(__file__).resolve().parents[4]


# --------------------------------------------------------------------------------------------
# Builders
# --------------------------------------------------------------------------------------------

def _canon() -> StoryModel:
    return StoryModel(
        premise=Premise(spark="a body in the gorge", central_question="can he resist?",
                        thesis="guilt administered", why_this_author="chance vs plan"),
        author_id="duerrenmatt",
        characters={
            "stettler": Character(canonical_name="Dr. Konrad Stettler", aliases=["Stettler"],
                                  role=CharacterRole.PROTAGONIST, facts={"profession": "Amtsarzt"}),
        },
        constraints=Constraints(language="de", forbidden=["sentimental redemption"], chapter_count=3),
    )


def _brief() -> Brief:
    return Brief(author_id="duerrenmatt", spark="a death certificate", language="de",
                 forbidden=["sentimental redemption"], chapter_count=3)


def _ruling(kind=RulingKind.CORRECT_UNIT, **over) -> Ruling:
    base = dict(
        kind=kind,
        reasoning="canon says Rutz is the priest and the creditor; the prose made him two men",
        instruction="rewrite the flagged span so the creditor is Rutz himself",
        canon_amendment="",
        ground_truth_violation="",
        binding_summary="Rutz is one man: priest and private creditor.",
        specialist_task="",
    )
    base.update(over)
    return Ruling(**base)


@pytest.fixture
def novel(tmp_path) -> Path:
    """A novel dir with ground truth established: brief written, canon committed at v1."""
    novel = tmp_path / "novel"
    save_brief(_brief(), novel / "00_input")
    save_canon(_canon(), novel / "01_canon")
    return novel


def _adjudicator(llm, novel: Path, log: DecisionLog, **over) -> Adjudicator:
    return Adjudicator(llm, ground_truth=GroundTruth.load(novel), log=log, **over)


# --------------------------------------------------------------------------------------------
# Ground truth
# --------------------------------------------------------------------------------------------

def test_ground_truth_loads_the_locked_canon_not_the_current_one(novel):
    """Ground truth is canon as LOCKED at creation — later canon versions must not shadow it."""
    drifted = _canon().model_copy(update={"version": 7})
    drifted.characters["stettler"].facts["profession"] = "Notar"  # canon drifted after the fact
    save_canon(drifted, novel / "01_canon", snapshot=False)

    gt = GroundTruth.load(novel)
    assert gt.locked_canon.characters["stettler"].facts["profession"] == "Amtsarzt"
    assert gt.locked_canon.version == 1


def test_ground_truth_requires_a_locked_canon(tmp_path):
    bare = tmp_path / "empty"
    save_brief(_brief(), bare / "00_input")
    with pytest.raises(FileNotFoundError):
        GroundTruth.load(bare)


def test_ground_truth_prompt_carries_brief_and_locked_canon(novel):
    block = GroundTruth.load(novel).prompt_block()
    assert "IMMUTABLE GROUND TRUTH" in block
    assert "sentimental redemption" in block          # the brief's forbidden list
    assert "Dr. Konrad Stettler" in block             # the locked cast


# --------------------------------------------------------------------------------------------
# Permissibility — the structural constraint on amending canon
# --------------------------------------------------------------------------------------------

def test_amend_canon_without_a_quoted_ground_truth_clause_is_impermissible():
    bad = _ruling(RulingKind.AMEND_CANON, canon_amendment="make Rutz a creditor only")
    assert "quote the clause" in permissible(bad)


def test_amend_canon_with_a_quoted_clause_stands():
    ok = _ruling(
        RulingKind.AMEND_CANON,
        canon_amendment="set constraints.language to 'de'",
        ground_truth_violation="the brief says Language: de; canon says en",
    )
    assert permissible(ok) is None


def test_specialist_ruling_must_carry_the_subtask():
    assert "sub-task" in permissible(_ruling(RulingKind.SPAWN_SPECIALIST))


def test_every_ruling_must_say_what_to_do_and_what_is_settled():
    assert permissible(_ruling(instruction="  ")) is not None
    assert permissible(_ruling(binding_summary="")) is not None


def test_correct_the_unit_is_permissible_by_default():
    assert permissible(_ruling()) is None


# --------------------------------------------------------------------------------------------
# The decision log — convergence
# --------------------------------------------------------------------------------------------

def test_conflict_key_is_stable_under_whitespace_and_case():
    assert conflict_key("ch01", "Rutz  is TWO men") == conflict_key("ch01", "rutz is two men")
    assert conflict_key("ch01", "a") != conflict_key("ch02", "a")


def test_log_appends_and_reloads_from_disk(tmp_path):
    log = DecisionLog(tmp_path)
    log.append("ch01", "Rutz is two men", _ruling())

    reloaded = DecisionLog(tmp_path).records()
    assert len(reloaded) == 1 and reloaded[0].unit == "ch01"
    assert (tmp_path / "decisions.jsonl").exists()
    # append-only: a second ruling adds a line, it does not replace the first
    log.append("ch02", "another", _ruling())
    assert len((tmp_path / "decisions.jsonl").read_text().strip().splitlines()) == 2


def test_a_settled_conflict_is_never_re_adjudicated(novel):
    """The convergence guarantee: same conflict -> same ruling, and no model call at all."""
    log = DecisionLog(novel / "05_reports")
    llm = FakeStructuredLLM(responses=[_ruling()])
    adj = _adjudicator(llm, novel, log)

    first = asyncio.run(adj.rule(unit="ch01", conflict="Rutz is two men"))
    assert len(llm.calls) == 1

    second = asyncio.run(adj.rule(unit="ch01", conflict="Rutz  is  TWO men"))  # same conflict
    assert len(llm.calls) == 1                      # no second call — the ruling is binding
    assert second.key == first.key
    assert second.ruling.binding_summary == first.ruling.binding_summary


def test_prior_rulings_are_handed_to_the_adjudicator_as_binding_context(novel):
    log = DecisionLog(novel / "05_reports")
    log.append("ch01", "Rutz is two men", _ruling())
    llm = FakeStructuredLLM(responses=[_ruling()])

    asyncio.run(_adjudicator(llm, novel, log).rule(unit="ch02", conflict="a different conflict"))

    prompt = llm.calls[0].prompt
    assert "BINDING — never contradict or re-open these" in prompt
    assert "Rutz is one man" in prompt


# --------------------------------------------------------------------------------------------
# Adjudication
# --------------------------------------------------------------------------------------------

def test_ruling_is_grounded_in_ground_truth_and_forbids_bridging_facts(novel):
    llm = FakeStructuredLLM(responses=[_ruling()])
    asyncio.run(_adjudicator(llm, novel, DecisionLog(novel / "05_reports")).rule(
        unit="ch01", conflict="the prose says Rutz is dead", context="scene s2 flagged it"))

    prompt, system = llm.calls[0].prompt, llm.calls[0].system
    assert "IMMUTABLE GROUND TRUTH" in prompt
    assert "scene s2 flagged it" in prompt
    assert "may NOT invent a fact to bridge" in system
    assert "opus" == llm.calls[0].model          # adjudication is the expensive, careful call


def test_impermissible_ruling_is_retried_with_the_reason(novel):
    impermissible = _ruling(RulingKind.AMEND_CANON, canon_amendment="rewrite the premise")
    llm = FakeStructuredLLM(responses=[impermissible, _ruling()])

    record = asyncio.run(_adjudicator(llm, novel, DecisionLog(novel / "05_reports")).rule(
        unit="ch01", conflict="the premise is inconvenient"))

    assert record.ruling.kind == RulingKind.CORRECT_UNIT
    assert "was not permissible" in llm.calls[1].prompt
    assert "quote the clause" in llm.calls[1].prompt


def test_adjudication_fails_loudly_when_no_permissible_ruling_arrives(novel):
    impermissible = _ruling(RulingKind.AMEND_CANON, canon_amendment="rewrite the premise")
    llm = FakeStructuredLLM(responses=[impermissible, impermissible])

    with pytest.raises(AdjudicationFailed) as exc:
        asyncio.run(_adjudicator(llm, novel, DecisionLog(novel / "05_reports"), max_attempts=2).rule(
            unit="ch01", conflict="the premise is inconvenient"))

    assert exc.value.unit == "ch01"
    # nothing impermissible was logged as binding
    assert DecisionLog(novel / "05_reports").records() == []


# --------------------------------------------------------------------------------------------
# Quarantine + run report
# --------------------------------------------------------------------------------------------

def test_quarantine_records_and_reloads(tmp_path):
    q = QuarantineLog(tmp_path)
    q.add("ch03", "repair budget exhausted", ["micro_sense: unresolved contradiction"])

    reloaded = QuarantineLog(tmp_path)
    assert reloaded.units() == ["ch03"]
    assert reloaded.is_quarantined("ch03") and not reloaded.is_quarantined("ch01")
    assert (tmp_path / "quarantine.jsonl").exists()


def test_logs_work_in_memory_without_a_directory():
    """Unit tests and dry runs must not be forced to touch disk."""
    log, q = DecisionLog(None), QuarantineLog(None)
    log.append("u", "c", _ruling())
    q.add("u", "r", [])
    assert len(log.records()) == 1 and q.units() == ["u"]


def test_run_report_is_written(tmp_path):
    path = write_run_report(tmp_path, {"chapters": 3, "quarantined": []})
    payload = json.loads(path.read_text())
    assert payload["chapters"] == 3 and "at" in payload
