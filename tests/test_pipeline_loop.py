"""
Integration tests for the autonomous chapter loop: spec -> prose -> reconcile.

Run from the repo root:
    .venv/bin/python -m pytest tests/ -q

These are the tests for the properties that let the pipeline run unattended (DESIGN §6.5): an
escalation is adjudicated and the ruling binds the retry, a unit that cannot be made correct is
quarantined instead of shipped, and a contradiction found at reconcile time is ruled on rather than
absorbed into canon. Everything is offline.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import List
import pytest

from storica.brief import Brief, save_brief
from storica.canon import (
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
    load_canon,
    save_canon,
)
from storica.checkers import Decision, Verdict
from storica.checkers.base import CheckerIssue
from storica.canon.validation import Severity
from storica.drafts import load_chapter_draft
from storica.llm import FakeStructuredLLM
from storica.pipeline import (
    ChapterOutcome,
    adjudicate_flags,
    draft_chapter,
    reconcile_chapter_into_canon,
)
from storica.plan import (
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
from storica.reports import DecisionLog, QuarantineLog, Ruling, RulingKind
from storica.stages.reconcile import (
    CharacterFactExtract,
    AliasExtract,
    ChapterExtraction,
    ContradictionExtract,
    LedgerKind,
    LedgerObservation,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
AUTHORS_ROOT = REPO_ROOT / "authors"

PROSE = (
    "Der Amtsarzt legte das Formular auf den Tisch und las die Zeile noch einmal. "
    "Draussen stand der Nebel im Tal, und niemand sprach. Er nahm die Feder, setzte sie an "
    "und hielt inne, weil ihm einfiel, wessen Unterschrift verlangt wurde. Das Papier war "
    "trocken und roch nach Amtsstube. Er unterschrieb nicht. Noch nicht.\n"
) * 4


# --------------------------------------------------------------------------------------------
# Fixtures
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
                                 trajectory="hardens"),
            ),
            "rutz": Character(canonical_name="Pfarrer Johannes Rutz", aliases=["Rutz"],
                              role=CharacterRole.ANTAGONIST, facts={"office": "village priest"}),
        },
        motifs=[Motif(id="formula_echo", desc="the same phrase recurs", setup_ch=1, payoff_ch=2,
                      status=MotifStatus.PLANNED)],
        promises=[Promise(id="berta_question", desc="the unanswered question", made_ch=1,
                          kept_ch=2, status=PromiseStatus.OPEN)],
        constraints=Constraints(language="de", forbidden=["justice triumphs"], chapter_count=2),
    )


def _arc() -> MacroArc:
    return MacroArc(
        chapter_count=2,
        shape="A man who files his guilt is handed the chance to close the file for good.",
        acts=[Act(number=1, title="The body", chapters=[1, 2], purpose="the chance is offered")],
        turning_points=[TurningPoint(id="tp1", chapter=2, description="he signs",
                                     reverses="that he could still confess")],
        arc_beats=[ArcBeat(id="b1", character_id="stettler", chapter=1,
                           beat="is handed the certificate", advances="want")],
        motif_ids=["formula_echo"],
        promise_ids=["berta_question"],
        tension_curve=[TensionPoint(chapter=1, tension=3, note="the offer"),
                       TensionPoint(chapter=2, tension=9, note="the signature")],
    )


def _spec(chapter: int = 1) -> ChapterSpec:
    return ChapterSpec(
        chapter=chapter,
        title="Das Protokoll",
        purpose="Stettler is handed the one case he cannot file honestly.",
        pov_character_id="stettler",
        present_character_ids=["stettler"],
        advances_beats=["b1"],
        setups=["formula_echo"],
        payoffs=[],
        promises_made=["berta_question"],
        promises_kept=[],
        entry_state=[],
        exit_state=[StateFact(key="body:location", value="in the gorge, unexamined")],
        scenes=[SceneSpec(id="s1", location="setting", character_ids=["stettler"],
                          intent="carries b1: the certificate reaches him",
                          turn="he realises whose signature is required")],
    )


@pytest.fixture
def novel(tmp_path) -> Path:
    """A novel with ground truth locked, an arc, and a chapter 1 spec — ready to draft."""
    novel = tmp_path / "novel"
    save_brief(Brief(author_id="duerrenmatt", spark="a death certificate", language="de",
                     chapter_count=2), novel / "00_input")
    save_canon(_canon(), novel / "01_canon")
    save_macro_arc(_arc(), novel / "02_plan")
    save_chapter_spec(_spec(1), novel / "02_plan")
    return novel


class ScriptedChecker:
    """A prose checker whose verdicts are handed to it, so loop behaviour is deterministic."""

    name = "scripted"

    def __init__(self, verdicts: List[Verdict]):
        self.verdicts = list(verdicts)
        self.calls = 0

    async def check_prose(self, *, prose, canon, spec, author, scene=None) -> Verdict:
        self.calls += 1
        return self.verdicts.pop(0) if self.verdicts else _pass()


def _pass() -> Verdict:
    return Verdict(decision=Decision.PASS, summary="fine", issues=[], conflict="")


def _escalate(conflict: str) -> Verdict:
    return Verdict(decision=Decision.ESCALATE, summary="cannot resolve", issues=[], conflict=conflict)


def _revise(hint: str = "cut the editorial aside") -> Verdict:
    return Verdict(
        decision=Decision.REVISE, summary="needs work", conflict="",
        issues=[CheckerIssue(unit="P2", kind="micro-sense", severity=Severity.BLOCKING,
                             canon_ref="stettler", fix_hint=hint)],
    )


def _ruling(kind=RulingKind.CORRECT_UNIT, **over) -> Ruling:
    base = dict(
        kind=kind,
        reasoning="canon says Stettler is the Amtsarzt; the prose made him a notary",
        instruction="Stettler is the Amtsarzt. Do not call him a notary.",
        canon_amendment="",
        ground_truth_violation="",
        binding_summary="Stettler is the Amtsarzt, not a notary.",
        specialist_task="",
    )
    base.update(over)
    return Ruling(**base)


def _draft(novel: Path, llm, **over) -> ChapterOutcome:
    return asyncio.run(draft_chapter(
        novel_dir=novel, authors_root=AUTHORS_ROOT, chapter=1, llm=llm, **over))


# --------------------------------------------------------------------------------------------
# The happy path
# --------------------------------------------------------------------------------------------

def test_a_clean_chapter_is_written_to_disk(novel):
    llm = FakeStructuredLLM(texts=[PROSE])
    outcome = _draft(novel, llm, checkers=[ScriptedChecker([_pass(), _pass()])])

    assert not outcome.quarantined and outcome.draft
    assert load_chapter_draft(novel / "03_drafts", 1).startswith("# Das Protokoll")
    assert QuarantineLog(novel / "05_reports").units() == []


def test_the_previous_chapters_tail_rides_into_the_next(novel):
    save_chapter_spec(_spec(2), novel / "02_plan")
    (novel / "03_drafts").mkdir(parents=True, exist_ok=True)
    (novel / "03_drafts" / "ch01.md").write_text("# Eins\n\nEr unterschrieb nicht. Noch nicht.")

    llm = FakeStructuredLLM(texts=[PROSE])
    asyncio.run(draft_chapter(novel_dir=novel, authors_root=AUTHORS_ROOT, chapter=2, llm=llm,
                              checkers=[ScriptedChecker([])]))

    assert "Er unterschrieb nicht. Noch nicht." in llm.calls[0].prompt


# --------------------------------------------------------------------------------------------
# Escalation -> binding ruling -> bound retry
# --------------------------------------------------------------------------------------------

def test_an_escalation_is_adjudicated_and_the_ruling_binds_the_retry(novel):
    checker = ScriptedChecker([_escalate("the prose calls Stettler a notary; canon says Amtsarzt")])
    llm = FakeStructuredLLM(responses=[_ruling()], texts=[PROSE, PROSE])

    outcome = _draft(novel, llm, checkers=[checker])

    assert not outcome.quarantined
    assert len(outcome.rulings) == 1
    # the ruling was logged as binding, and the rewrite carried it
    assert DecisionLog(novel / "05_reports").records()[0].ruling.binding_summary.startswith("Stettler is")
    retry_prompt = llm.calls[-1].prompt
    assert "Binding ruling (already adjudicated" in retry_prompt
    assert "Do not call him a notary." in retry_prompt


def test_every_ruling_so_far_binds_the_next_attempt(novel):
    """A second escalation must not make the chapter forget what the first one settled."""
    checker = ScriptedChecker([_escalate("conflict A"), _escalate("conflict B")])
    first = _ruling(instruction="Stettler is the Amtsarzt. Do not call him a notary.")
    second = _ruling(instruction="The certificate is signed on the second evening, not the first.",
                     binding_summary="signed on the second evening")
    llm = FakeStructuredLLM(responses=[first, second], texts=[PROSE, PROSE, PROSE])

    outcome = _draft(novel, llm, checkers=[checker], max_escalations=2)

    assert not outcome.quarantined and len(outcome.rulings) == 2
    third_attempt = llm.calls[-1].prompt
    assert "Do not call him a notary." in third_attempt
    assert "second evening, not the first" in third_attempt
    # the adjudicator was shown what the checker actually found, not just a label
    assert "cannot resolve" in llm.calls[1].prompt


def test_repeated_escalation_is_bounded_and_quarantines(novel):
    checker = ScriptedChecker([_escalate("conflict A"), _escalate("conflict B"), _escalate("conflict C")])
    llm = FakeStructuredLLM(responses=[_ruling(), _ruling()], texts=[PROSE, PROSE, PROSE])

    outcome = _draft(novel, llm, checkers=[checker], max_escalations=2)

    assert outcome.quarantined and "escalated" in outcome.reason
    assert QuarantineLog(novel / "05_reports").is_quarantined("ch01")
    assert not (novel / "03_drafts" / "ch01.md").exists()   # never shipped


def test_a_ruling_that_would_amend_canon_quarantines_rather_than_rewriting_canon(novel):
    """The v1 ratchet in one test: a chapter-level conflict must never edit canon by itself."""
    checker = ScriptedChecker([_escalate("canon has the wrong profession")])
    amend = _ruling(RulingKind.AMEND_CANON, canon_amendment="set stettler.profession to Notar",
                    ground_truth_violation="the brief calls him a notary")
    llm = FakeStructuredLLM(responses=[amend], texts=[PROSE])

    outcome = _draft(novel, llm, checkers=[checker])

    assert outcome.quarantined and "canon amendment" in outcome.reason
    assert load_canon(novel / "01_canon").characters["stettler"].facts["profession"] == "Amtsarzt"


def test_exhausted_repair_budget_quarantines_with_the_issues_recorded(novel):
    checker = ScriptedChecker([_revise(), _revise(), _revise(), _revise()])
    llm = FakeStructuredLLM(texts=[PROSE, PROSE, PROSE, PROSE])

    outcome = _draft(novel, llm, checkers=[checker], max_repairs=2)

    assert outcome.quarantined and outcome.reason == "prose repair budget exhausted"
    record = QuarantineLog(novel / "05_reports").records()[0]
    assert record.unit == "ch01" and record.issues


# --------------------------------------------------------------------------------------------
# Reconcile + adjudication of what the draft disagreed with
# --------------------------------------------------------------------------------------------

def _extraction(**over) -> ChapterExtraction:
    base = dict(
        character_facts=[], aliases=[], world_facts=[], timeline=[], contradictions=[],
        ledger=[
            LedgerObservation(id="formula_echo", kind=LedgerKind.MOTIF_SETUP, landed=True,
                              evidence="the phrase recurs"),
            LedgerObservation(id="berta_question", kind=LedgerKind.PROMISE_MADE, landed=True,
                              evidence="she asks"),
        ],
    )
    base.update(over)
    return ChapterExtraction(**base)


def _drafted(novel: Path) -> None:
    (novel / "03_drafts").mkdir(parents=True, exist_ok=True)
    (novel / "03_drafts" / "ch01.md").write_text(PROSE, encoding="utf-8")


def test_reconcile_commits_canon_and_advances_the_ledger(novel):
    _drafted(novel)
    llm = FakeStructuredLLM(responses=[_extraction()])

    result = asyncio.run(reconcile_chapter_into_canon(novel_dir=novel, chapter=1, llm=llm))

    on_disk = load_canon(novel / "01_canon")
    assert on_disk.version == 2                                    # the reconcile is a canon change
    assert on_disk.motifs[0].status == MotifStatus.SETUP
    assert result.is_valid


def test_a_contradiction_is_adjudicated_and_canon_keeps_its_fact(novel):
    """The inverse of v1's guardian: the prose does not get to overwrite canon by saying so."""
    _drafted(novel)
    extraction = _extraction(contradictions=[ContradictionExtract(
        canon_ref="rutz", canon_says="office: village priest",
        prose_says="Rutz is the village creditor", evidence="der Gläubiger Rutz")])
    llm = FakeStructuredLLM(responses=[extraction, _ruling()], texts=[PROSE + "\nKorrigiert."])

    result = asyncio.run(reconcile_chapter_into_canon(novel_dir=novel, chapter=1, llm=llm))

    assert load_canon(novel / "01_canon").characters["rutz"].facts["office"] == "village priest"
    assert any(f.kind.value == "contradiction" for f in result.flagged)
    logged = DecisionLog(novel / "05_reports").records()
    assert len(logged) == 1 and "rutz" in logged[0].unit


def test_a_correct_the_unit_ruling_repairs_the_saved_draft(novel):
    """A ruling that says the draft is wrong must reach the draft — not only the log."""
    _drafted(novel)
    extraction = _extraction(contradictions=[ContradictionExtract(
        canon_ref="rutz", canon_says="office: village priest",
        prose_says="Rutz is the village creditor", evidence="der Gläubiger Rutz")])
    llm = FakeStructuredLLM(responses=[extraction, _ruling()], texts=[PROSE + "\nKorrigiert."])

    asyncio.run(reconcile_chapter_into_canon(novel_dir=novel, chapter=1, llm=llm))

    repair = llm.calls[-1]
    assert repair.schema == "<text>"
    assert "Do not call him a notary." in repair.prompt              # the ruling's instruction
    assert "Canon slice (SOURCE OF TRUTH" in repair.prompt           # grounded like every repair
    assert load_chapter_draft(novel / "03_drafts", 1).endswith("Korrigiert.")
    assert load_canon(novel / "01_canon").version == 2               # canon still committed


def test_a_stub_ruling_repair_is_discarded_and_the_draft_kept(novel):
    _drafted(novel)
    extraction = _extraction(contradictions=[ContradictionExtract(
        canon_ref="rutz", canon_says="office: village priest",
        prose_says="creditor", evidence="x")])
    llm = FakeStructuredLLM(responses=[extraction, _ruling()], texts=["zu kurz"])

    asyncio.run(reconcile_chapter_into_canon(novel_dir=novel, chapter=1, llm=llm))

    assert load_chapter_draft(novel / "03_drafts", 1) == PROSE


def test_an_amend_canon_ruling_at_reconcile_quarantines_and_commits_nothing(novel):
    """An excluded chapter must not leave its facts behind in canon."""
    _drafted(novel)
    extraction = _extraction(
        character_facts=[CharacterFactExtract(character_id="stettler", surface_name="Stettler",
                                              key="habit", value="counts the steps", evidence="x")],
        contradictions=[ContradictionExtract(
            canon_ref="stettler", canon_says="profession: Amtsarzt",
            prose_says="Notar", evidence="der Notar Stettler")],
    )
    amend = _ruling(RulingKind.AMEND_CANON, canon_amendment="set stettler.profession to Notar",
                    ground_truth_violation="the brief calls him a notary")
    llm = FakeStructuredLLM(responses=[extraction, amend])

    asyncio.run(reconcile_chapter_into_canon(novel_dir=novel, chapter=1, llm=llm))

    log = QuarantineLog(novel / "05_reports")
    assert log.is_quarantined("ch01") and "canon amendment" in log.records()[0].reason
    canon = load_canon(novel / "01_canon")
    assert canon.version == 1 and "habit" not in canon.characters["stettler"].facts


def test_an_alias_collision_is_adjudicated_too(novel):
    _drafted(novel)
    extraction = _extraction(aliases=[AliasExtract(
        character_id="rutz", alias="der Amtsarzt", evidence="der Amtsarzt Rutz")])
    llm = FakeStructuredLLM(responses=[extraction, _ruling()], texts=[PROSE])

    result = asyncio.run(reconcile_chapter_into_canon(novel_dir=novel, chapter=1, llm=llm))

    assert any(f.kind.value == "alias_collision" for f in result.flagged)
    assert "der Amtsarzt" not in load_canon(novel / "01_canon").characters["rutz"].aliases
    assert len(DecisionLog(novel / "05_reports").records()) == 1


def test_ledger_and_planning_flags_are_not_adjudicated(novel):
    """A motif that did not land is a planning problem, not a dispute about what is true."""
    _drafted(novel)
    extraction = _extraction(ledger=[
        LedgerObservation(id="formula_echo", kind=LedgerKind.MOTIF_SETUP, landed=False,
                          evidence="the phrase never appears"),
        LedgerObservation(id="berta_question", kind=LedgerKind.PROMISE_MADE, landed=True,
                          evidence="she asks"),
    ])
    llm = FakeStructuredLLM(responses=[extraction])

    result = asyncio.run(reconcile_chapter_into_canon(novel_dir=novel, chapter=1, llm=llm))

    assert any(f.kind.value == "ledger_missing" for f in result.flagged)
    assert load_canon(novel / "01_canon").motifs[0].status == MotifStatus.PLANNED  # not advanced
    assert DecisionLog(novel / "05_reports").records() == []                       # no ruling needed


def test_the_same_contradiction_twice_reuses_the_first_ruling(novel):
    """Convergence across chapters: a settled conflict costs nothing the second time."""
    _drafted(novel)
    contradiction = ContradictionExtract(
        canon_ref="rutz", canon_says="office: village priest",
        prose_says="Rutz is the village creditor", evidence="der Gläubiger")
    llm = FakeStructuredLLM(responses=[_ruling()])

    flags_seen = asyncio.run(adjudicate_flags(
        novel_dir=novel, chapter=1, llm=llm,
        flags=[_flag_from(contradiction), _flag_from(contradiction)]))

    assert len(flags_seen) == 2
    assert flags_seen[0].key == flags_seen[1].key
    assert len(llm.calls) == 1                                   # ruled once, applied twice


def _flag_from(c: ContradictionExtract):
    from storica.stages.reconcile import Flag, FlagKind

    return Flag(kind=FlagKind.CONTRADICTION, ref=c.canon_ref,
                reason=f"the draft contradicts canon at '{c.canon_ref}'",
                canon_says=c.canon_says, prose_says=c.prose_says, evidence=c.evidence)


def test_trace_and_reports_are_on_disk_after_a_chapter(novel):
    llm = FakeStructuredLLM(texts=[PROSE])
    _draft(novel, llm, checkers=[ScriptedChecker([])])

    records = [json.loads(p.read_text()) for p in sorted((novel / "04_trace").glob("*.json"))]
    assert records, "every generation must leave a trace"

    # Every generation call is auditable: prompt in, artifact out. The assembled-chapter record is
    # a snapshot rather than a call, so it carries an artifact and no prompt — that is the one
    # record allowed to have an empty prompt.
    generations = [r for r in records if r["stage"].endswith("_prose")]
    assert generations and all(r["prompt"] and r["artifact"] for r in generations)
    assert any(r["stage"].endswith("_prose_assembled") and r["artifact"] for r in records)
