"""
End-to-end tests for the run loop and the CLI.

Run from the backend/ directory:
    venv/bin/python -m pytest app/v2/tests/ -q

The property that matters most here is **resumability**: every stage asks the filesystem whether
its artifact exists and skips it if so, because a replay-driven run stops on every unanswered call
and restarts hundreds of times. A stage that redid its work on resume would make that unusable.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from app.v2.brief import Brief, save_brief
from app.v2.canon import (
    Character,
    CharacterArc,
    CharacterRole,
    Constraints,
    Motif,
    MotifStatus,
    Premise,
    Promise,
    PromiseStatus,
    StoryModel,
    save_canon,
)
from app.v2.checkers import Decision, Verdict
from app.v2.cli import main
from app.v2.drivers import ReplayLLM, ResponseNeeded
from app.v2.llm import FakeStructuredLLM
from app.v2.plan import (
    Act,
    ArcBeat,
    ChapterSpec,
    MacroArc,
    SceneSpec,
    StateFact,
    TensionPoint,
    TurningPoint,
    save_chapter_spec,
    save_macro_arc,
)
from app.v2.reports import QuarantineLog
from app.v2.runner import RunState, run_novel
from app.v2.stages.reconcile import ChapterExtraction, LedgerKind, LedgerObservation

REPO_ROOT = Path(__file__).resolve().parents[4]
AUTHORS_ROOT = REPO_ROOT / "authors"

PROSE = (
    "Der Amtsarzt legte das Formular auf den Tisch und las die Zeile noch einmal. "
    "Draussen stand der Nebel im Tal. Er nahm die Feder und hielt inne, weil ihm einfiel, "
    "wessen Unterschrift verlangt wurde. Er unterschrieb nicht. Noch nicht.\n"
) * 4


# --------------------------------------------------------------------------------------------
# A one-chapter novel, fully planned, so the run loop starts at stage 5
# --------------------------------------------------------------------------------------------

def _canon() -> StoryModel:
    return StoryModel(
        premise=Premise(spark="a body in the gorge", central_question="can he resist?",
                        thesis="guilt administered", why_this_author="chance vs plan"),
        author_id="duerrenmatt",
        characters={
            "stettler": Character(
                canonical_name="Dr. Konrad Stettler", aliases=["Stettler", "der Amtsarzt"],
                role=CharacterRole.PROTAGONIST, facts={"profession": "Amtsarzt"},
                arc=CharacterArc(want="close the case", need="confess", flaw="order",
                                 trajectory="hardens")),
        },
        motifs=[Motif(id="formula_echo", desc="the phrase recurs", setup_ch=1, payoff_ch=1,
                      status=MotifStatus.PLANNED)],
        promises=[Promise(id="berta_question", desc="the unanswered question", made_ch=1,
                          kept_ch=1, status=PromiseStatus.OPEN)],
        constraints=Constraints(language="de", forbidden=["justice triumphs"], chapter_count=1),
    )


def _arc() -> MacroArc:
    return MacroArc(
        chapter_count=1,
        shape="A man who files his guilt is handed the chance to close the file for good.",
        acts=[Act(number=1, title="The body", chapters=[1], purpose="the chance is offered")],
        turning_points=[TurningPoint(id="tp1", chapter=1, description="he is handed it",
                                     reverses="that the case was routine")],
        arc_beats=[ArcBeat(id="b1", character_id="stettler", chapter=1,
                           beat="is handed the certificate", advances="want")],
        motif_ids=["formula_echo"], promise_ids=["berta_question"],
        tension_curve=[TensionPoint(chapter=1, tension=5, note="the offer")],
    )


def _spec() -> ChapterSpec:
    return ChapterSpec(
        chapter=1, title="Das Protokoll",
        purpose="Stettler is handed the one case he cannot file honestly.",
        pov_character_id="stettler", present_character_ids=["stettler"],
        advances_beats=["b1"], setups=["formula_echo"], payoffs=["formula_echo"],
        promises_made=["berta_question"], promises_kept=["berta_question"],
        entry_state=[], exit_state=[StateFact(key="body:location", value="in the gorge")],
        scenes=[SceneSpec(id="s1", location="setting", character_ids=["stettler"],
                          intent="carries b1", turn="he sees whose signature is required")],
    )


def _extraction() -> ChapterExtraction:
    return ChapterExtraction(
        character_facts=[], aliases=[], world_facts=[], timeline=[], contradictions=[],
        ledger=[
            LedgerObservation(id="formula_echo", kind=LedgerKind.MOTIF_SETUP, landed=True, evidence="x"),
            LedgerObservation(id="formula_echo", kind=LedgerKind.MOTIF_PAYOFF, landed=True, evidence="x"),
            LedgerObservation(id="berta_question", kind=LedgerKind.PROMISE_MADE, landed=True, evidence="x"),
            LedgerObservation(id="berta_question", kind=LedgerKind.PROMISE_KEPT, landed=True, evidence="x"),
        ],
    )


@pytest.fixture
def planned(tmp_path) -> Path:
    novel = tmp_path / "novel"
    save_brief(Brief(author_id="duerrenmatt", spark="a death certificate", language="de",
                     chapter_count=1), novel / "00_input")
    save_canon(_canon(), novel / "01_canon")
    save_macro_arc(_arc(), novel / "02_plan")
    save_chapter_spec(_spec(), novel / "02_plan")
    return novel


def _verdict(decision=Decision.PASS) -> Verdict:
    return Verdict(decision=decision, summary="the book holds", issues=[], conflict="")


# --------------------------------------------------------------------------------------------
# The whole loop
# --------------------------------------------------------------------------------------------

def test_run_produces_a_novel_and_a_report(planned):
    llm = FakeStructuredLLM(responses=[_extraction(), _verdict()], texts=[PROSE])

    result = asyncio.run(run_novel(novel_dir=planned, authors_root=AUTHORS_ROOT, llm=llm,
                                   checkers=[]))

    assert result.chapters == [1]
    assert result.novel_path == planned / "novel.md"
    assert "Das Protokoll" in (planned / "novel.md").read_text()
    assert result.audit_decision == "pass"

    report = json.loads((planned / "05_reports" / "run_report.json").read_text())
    assert report["chapters_included"] == [1]
    assert report["canon_version"] == 2          # the reconcile committed a canon change


def test_reconcile_advances_the_ledger_through_the_run(planned):
    llm = FakeStructuredLLM(responses=[_extraction(), _verdict()], texts=[PROSE])
    asyncio.run(run_novel(novel_dir=planned, authors_root=AUTHORS_ROOT, llm=llm, checkers=[]))

    from app.v2.canon import load_canon
    canon = load_canon(planned / "01_canon")
    assert canon.motifs[0].status == MotifStatus.PAID_OFF
    assert canon.promises[0].status == PromiseStatus.KEPT


def test_a_second_run_redoes_nothing(planned):
    """Resumability: the artifacts on disk are the progress record."""
    llm = FakeStructuredLLM(responses=[_extraction(), _verdict()], texts=[PROSE])
    asyncio.run(run_novel(novel_dir=planned, authors_root=AUTHORS_ROOT, llm=llm, checkers=[]))

    second = FakeStructuredLLM(responses=[_verdict()], texts=[])   # no prose, no extraction queued
    result = asyncio.run(run_novel(novel_dir=planned, authors_root=AUTHORS_ROOT, llm=second,
                                   checkers=[]))

    assert result.chapters == [1]
    assert not any(c.schema == "<text>" for c in second.calls)   # no chapter was re-written
    assert RunState.load(planned / "05_reports").reconciled == [1]


def test_a_quarantined_chapter_is_excluded_from_the_book(planned):
    class Escalating:
        name = "escalating"

        async def check_prose(self, *, prose, canon, spec, author, scene=None):
            return Verdict(decision=Decision.ESCALATE, summary="no", issues=[],
                           conflict="canon cannot support this chapter")

    # adjudication is attempted twice, then the chapter is quarantined
    from app.v2.reports import Ruling, RulingKind
    ruling = Ruling(kind=RulingKind.CORRECT_UNIT, reasoning="r", instruction="fix it",
                    canon_amendment="", ground_truth_violation="", binding_summary="settled",
                    specialist_task="")
    llm = FakeStructuredLLM(responses=[ruling, ruling, _verdict()], texts=[PROSE, PROSE, PROSE])

    result = asyncio.run(run_novel(novel_dir=planned, authors_root=AUTHORS_ROOT, llm=llm,
                                   checkers=[Escalating()]))

    assert result.quarantined == ["ch01"]
    assert result.chapters == []
    assert QuarantineLog(planned / "05_reports").is_quarantined("ch01")


def test_audit_can_be_skipped(planned):
    llm = FakeStructuredLLM(responses=[_extraction()], texts=[PROSE])
    result = asyncio.run(run_novel(novel_dir=planned, authors_root=AUTHORS_ROOT, llm=llm,
                                   checkers=[], audit=False))
    assert result.audit_decision == "" and result.novel_path is not None


# --------------------------------------------------------------------------------------------
# Driving the run with the replay driver — no API key
# --------------------------------------------------------------------------------------------

def test_a_replay_driven_run_pauses_and_resumes(planned):
    """The agent-in-the-loop workflow, end to end: pause, answer on disk, run again, finish."""
    session = planned / "06_session"

    with pytest.raises(ResponseNeeded) as pause:
        asyncio.run(run_novel(novel_dir=planned, authors_root=AUTHORS_ROOT,
                              llm=ReplayLLM(session), checkers=[], audit=False))

    # the request is the real prose prompt, grounded in canon
    request = pause.value.request_path.read_text()
    assert "Canon slice (SOURCE OF TRUTH" in request and "Das Protokoll" in request
    pause.value.response_path.write_text(PROSE, encoding="utf-8")

    # next call needed: the reconcile extraction (a schema call, not prose)
    with pytest.raises(ResponseNeeded) as second:
        asyncio.run(run_novel(novel_dir=planned, authors_root=AUTHORS_ROOT,
                              llm=ReplayLLM(session), checkers=[], audit=False))
    assert not second.value.is_text
    second.value.response_path.write_text(_extraction().model_dump_json(), encoding="utf-8")

    result = asyncio.run(run_novel(novel_dir=planned, authors_root=AUTHORS_ROOT,
                                   llm=ReplayLLM(session), checkers=[], audit=False))
    assert result.chapters == [1] and (planned / "novel.md").exists()


# --------------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------------

def test_cli_new_creates_the_skeleton_and_brief(tmp_path, capsys):
    target = tmp_path / "novels" / "test-novel"
    assert main(["new", str(target), "--author", "duerrenmatt", "--spark", "a certificate",
                 "--language", "de", "--chapters", "3"]) == 0

    assert (target / "00_input" / "brief.yaml").exists()
    for sub in ("01_canon", "02_plan/chapters", "03_drafts", "04_trace", "05_reports"):
        assert (target / sub).is_dir()
    assert "edit the brief" in capsys.readouterr().out


def test_cli_new_refuses_to_overwrite_ground_truth(tmp_path, capsys):
    target = tmp_path / "novel"
    main(["new", str(target), "--author", "duerrenmatt"])
    assert main(["new", str(target), "--author", "duerrenmatt"]) == 1
    assert "immutable" in capsys.readouterr().out


def test_cli_status_reports_progress(planned, capsys):
    assert main(["status", str(planned)]) == 0
    out = capsys.readouterr().out
    assert "canon:    v1" in out
    assert "1 motifs" in out and "specced:  [1]" in out
    assert "drafted:  (none)" in out


def test_cli_run_reports_a_pause_rather_than_crashing(planned, capsys):
    assert main(["run", str(planned), "--driver", "replay", "--authors", str(AUTHORS_ROOT),
                 "--no-audit"]) == 2
    assert "[paused]" in capsys.readouterr().out
