"""
Tests for P6: assembly and the Final Auditor.

Run from the backend/ directory:
    .venv/bin/python -m pytest tests/ -q

Offline: the auditor is driven by `FakeStructuredLLM` with a pre-built `Verdict`, so what is under
test is our contract — what ships into the book, what is refused, and what the last reader is
handed — not the model's judgement. Sync tests drive the coroutines with `asyncio.run`.
"""

from __future__ import annotations

import asyncio

import pytest

from storica.assembly import CHAPTER_SEPARATOR, assemble_novel, save_novel
from storica.canon import (
    Character,
    CharacterRole,
    Constraints,
    Motif,
    MotifStatus,
    Premise,
    Promise,
    PromiseStatus,
    Severity,
    StoryModel,
)
from storica.checkers.auditor import FinalAuditor, audit_ledger
from storica.checkers.base import CheckerIssue, Decision, Verdict
from storica.drafts import save_chapter_draft
from storica.llm import FakeStructuredLLM
from storica.plan import Act, MacroArc, TensionPoint, TurningPoint
from storica.reports import QuarantineLog
from storica.trace import Tracer


# --------------------------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------------------------

@pytest.fixture
def canon() -> StoryModel:
    return StoryModel(
        premise=Premise(
            spark="A death certificate the wrong man has to sign.",
            central_question="Kann ein Formular jemanden freisprechen?",
            thesis="Bureaucracy absolves nobody.",
            why_this_author="Justice by accident.",
        ),
        author_id="duerrenmatt",
        characters={
            "stettler": Character(
                canonical_name="Dr. Konrad Stettler",
                aliases=["der Amtsarzt"],
                role=CharacterRole.PROTAGONIST,
                facts={"profession": "Amtsarzt"},
            )
        },
        world_facts={"setting": "Lauenegg, Graubünden"},
        motifs=[Motif(id="formula_echo", desc="the phrase recurs identically",
                      setup_ch=1, payoff_ch=3, status=MotifStatus.PAID_OFF)],
        promises=[Promise(id="berta_question", desc="Berta's unanswered question",
                          made_ch=1, kept_ch=3, status=PromiseStatus.KEPT)],
        constraints=Constraints(language="de", chapter_count=3),
    )


@pytest.fixture
def arc() -> MacroArc:
    return MacroArc(
        chapter_count=3,
        shape="A doctor signs, is asked, and does not answer.",
        acts=[
            Act(number=1, title="Das Formular", chapters=[1, 2], purpose="The lie is signed."),
            Act(number=2, title="Die Frage", chapters=[3], purpose="The lie is named."),
        ],
        turning_points=[TurningPoint(id="tp1", chapter=3, description="Berta asks",
                                     reverses="that silence costs nothing")],
        arc_beats=[],
        motif_ids=["formula_echo"],
        promise_ids=["berta_question"],
        tension_curve=[TensionPoint(chapter=n, tension=n + 3, note="pressure") for n in (1, 2, 3)],
    )


def draft(drafts_dir, chapter: int) -> str:
    text = f"# Kapitel {chapter}\n\nStettler legte das Formular {chapter} auf den Tisch.\n"
    save_chapter_draft(text, drafts_dir, chapter)
    return text


def _verdict(decision: Decision = Decision.PASS, conflict: str = "") -> Verdict:
    return Verdict(
        decision=decision,
        summary="the book coheres and answers its question",
        issues=[
            CheckerIssue(unit="ch02 vs ch09", kind="coherence", severity=Severity.WARNING,
                         canon_ref="stettler", fix_hint="correct the age in ch09")
        ],
        conflict=conflict,
    )


def _audit(auditor: FinalAuditor, *, canon, arc, novel_text="# Kapitel 1\n\nText.", quarantined=()) -> Verdict:
    return asyncio.run(
        auditor.audit(novel_text=novel_text, canon=canon, arc=arc, quarantined=quarantined)
    )


# --------------------------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------------------------

def test_assembly_concatenates_the_drafted_chapters_in_order(tmp_path, canon, arc):
    for n in (2, 1, 3):  # written out of order on disk; the book is still in reading order
        draft(tmp_path, n)

    result = assemble_novel(canon=canon, arc=arc, drafts_dir=tmp_path, title="Der Chrachen")

    assert result.chapters == [1, 2, 3]
    assert result.excluded == []
    assert result.issues == []
    assert result.text.startswith("# Der Chrachen\n\n# Kapitel 1")
    assert result.text.index("Formular 1") < result.text.index("Formular 2") < result.text.index("Formular 3")
    assert result.text.count(CHAPTER_SEPARATOR) == 2  # one seam between each pair of chapters


def test_assembly_does_not_reformat_the_prose(tmp_path, canon, arc):
    """The prose was written from canon and checked; editing it here would be an unchecked rewrite."""
    for n in (1, 2, 3):
        draft(tmp_path, n)

    text = assemble_novel(canon=canon, arc=arc, drafts_dir=tmp_path).text

    assert "# Kapitel 2\n\nStettler legte das Formular 2 auf den Tisch." in text


def test_quarantined_chapter_is_excluded_and_reported(tmp_path, canon, arc):
    """§6.5: a unit that exhausted its repair budget is dropped, not shipped broken."""
    for n in (1, 2, 3):
        draft(tmp_path, n)
    quarantine = QuarantineLog(None)
    quarantine.add("ch02", "repair budget exhausted", ["micro_sense.grounding"])

    result = assemble_novel(canon=canon, arc=arc, drafts_dir=tmp_path, quarantine=quarantine)

    assert result.chapters == [1, 3]
    assert result.excluded == [2]
    assert "Formular 2" not in result.text
    assert [i.code for i in result.issues] == ["assembly.quarantined"]
    assert result.issues[0].severity == Severity.BLOCKING
    assert not result.is_complete


def test_planned_but_undrafted_chapter_is_blocking(tmp_path, canon, arc):
    for n in (1, 2):
        draft(tmp_path, n)

    result = assemble_novel(canon=canon, arc=arc, drafts_dir=tmp_path)

    assert result.chapters == [1, 2]
    assert result.excluded == [3]
    assert [i.severity for i in result.issues] == [Severity.BLOCKING]


def test_mid_book_gap_is_reported_apart_from_a_missing_ending(tmp_path, canon, arc):
    """A truncated book stops; a holed book asks the reader to cross a discontinuity."""
    holed = tmp_path / "holed"
    for n in (1, 3):
        draft(holed, n)
    gap = assemble_novel(canon=canon, arc=arc, drafts_dir=holed)

    truncated = tmp_path / "truncated"
    for n in (1, 2):
        draft(truncated, n)
    ending = assemble_novel(canon=canon, arc=arc, drafts_dir=truncated)

    assert [i.code for i in gap.issues] == ["assembly.gap"]
    assert "middle of the book" in gap.issues[0].message
    assert "worse than a missing ending" in gap.issues[0].message
    assert [i.code for i in ending.issues] == ["assembly.missing_ending"]
    assert "stops at chapter 2 of 3" in ending.issues[0].message


def test_assembly_of_nothing_is_empty_and_blocking(tmp_path, canon, arc):
    result = assemble_novel(canon=canon, arc=arc, drafts_dir=tmp_path)

    assert result.text == ""
    assert result.chapters == []
    assert result.excluded == [1, 2, 3]
    assert not result.is_complete


def test_save_novel_writes_novel_md_at_the_novel_root(tmp_path, canon, arc):
    drafts = tmp_path / "03_drafts"
    draft(drafts, 1)
    result = assemble_novel(canon=canon, arc=arc, drafts_dir=drafts, title="Der Chrachen")

    path = save_novel(result.text, tmp_path)

    assert path == tmp_path / "novel.md"
    assert path.read_text(encoding="utf-8") == result.text


# --------------------------------------------------------------------------------------------
# The deterministic ledger pre-check
# --------------------------------------------------------------------------------------------

def test_audit_ledger_is_silent_on_a_clean_ledger(canon):
    assert audit_ledger(canon) == []


def test_audit_ledger_finds_an_open_promise(canon):
    canon.promises[0].status = PromiseStatus.OPEN
    canon.promises[0].kept_ch = None

    issues = audit_ledger(canon)

    assert [i.code for i in issues] == ["audit.promise_open"]
    assert issues[0].severity == Severity.BLOCKING
    assert issues[0].ref == "berta_question"


def test_audit_ledger_finds_a_motif_that_was_planted_and_never_paid_off(canon):
    canon.motifs[0].status = MotifStatus.SETUP

    issues = audit_ledger(canon)

    assert [i.code for i in issues] == ["audit.motif_unpaid"]
    assert issues[0].severity == Severity.BLOCKING


def test_audit_ledger_warns_rather_than_blocks_on_deliberate_breaks(canon):
    """A promise broken on the page is legitimate; only the auditor can tell whether it is."""
    canon.promises[0].status = PromiseStatus.BROKEN
    canon.motifs[0].status = MotifStatus.DROPPED

    severities = {i.severity for i in audit_ledger(canon)}

    assert severities == {Severity.WARNING}


# --------------------------------------------------------------------------------------------
# The Final Auditor
# --------------------------------------------------------------------------------------------

def test_auditor_returns_the_verdict_it_is_given(canon, arc):
    given = _verdict()
    llm = FakeStructuredLLM(responses=[given])

    verdict = _audit(FinalAuditor(llm), canon=canon, arc=arc)

    assert verdict is given
    assert llm.calls[0].schema == "Verdict"
    assert llm.calls[0].model == "opus"


def test_auditor_records_the_audit_in_the_trace(tmp_path, canon, arc):
    """The last gate of an unwatched run has to be reconstructable afterwards (§6.5)."""
    llm = FakeStructuredLLM(responses=[_verdict()])

    _audit(FinalAuditor(llm, tracer=Tracer(tmp_path)), canon=canon, arc=arc)

    written = list(tmp_path.glob("*.json"))
    assert len(written) == 1
    assert written[0].name.endswith("final_audit_novel.json")


def test_audit_prompt_carries_the_book_the_canon_and_the_arc(canon, arc):
    llm = FakeStructuredLLM(responses=[_verdict()])

    _audit(FinalAuditor(llm), canon=canon, arc=arc, novel_text="# Kapitel 1\n\nDas Formular lag da.")
    prompt = llm.calls[0].prompt

    assert "# Canon slice (SOURCE OF TRUTH" in prompt
    assert "Dr. Konrad Stettler" in prompt
    assert "der Amtsarzt" in prompt
    assert arc.shape in prompt
    assert "act 1 — Das Formular" in prompt
    assert "Das Formular lag da." in prompt


def test_audit_prompt_states_the_central_question_as_the_contract(canon, arc):
    llm = FakeStructuredLLM(responses=[_verdict()])

    _audit(FinalAuditor(llm), canon=canon, arc=arc)
    prompt = llm.calls[0].prompt

    assert "# The contract with the reader" in prompt
    assert canon.premise.central_question in prompt
    assert "ending answer the central question" in prompt


def test_audit_prompt_hands_over_the_ledger_findings(canon, arc):
    """Cheap before expensive: the auditor reads with the bookkeeping already done."""
    canon.promises[0].status = PromiseStatus.OPEN
    llm = FakeStructuredLLM(responses=[_verdict()])

    _audit(FinalAuditor(llm), canon=canon, arc=arc)
    prompt = llm.calls[0].prompt

    assert "# Ledger findings (mechanical pre-check" in prompt
    assert "audit.promise_open" in prompt
    assert "berta_question" in prompt


def test_audit_prompt_says_the_ledger_is_clean_when_it_is(canon, arc):
    llm = FakeStructuredLLM(responses=[_verdict()])

    _audit(FinalAuditor(llm), canon=canon, arc=arc)

    assert "The ledger is clean" in llm.calls[0].prompt


def test_quarantined_units_make_the_audit_say_the_book_is_not_done(canon, arc):
    llm = FakeStructuredLLM(responses=[_verdict()])

    _audit(FinalAuditor(llm), canon=canon, arc=arc, quarantined=["ch02"])
    prompt = llm.calls[0].prompt

    assert "THE BOOK IS NOT DONE" in prompt
    assert "- ch02" in prompt
    assert "blocking on its own" in prompt


def test_empty_quarantine_says_nothing_is_missing(canon, arc):
    llm = FakeStructuredLLM(responses=[_verdict()])

    _audit(FinalAuditor(llm), canon=canon, arc=arc)

    assert "(none — every planned unit is present" in llm.calls[0].prompt


def test_auditor_reads_as_a_fresh_reader_and_never_scores(canon, arc):
    llm = FakeStructuredLLM(responses=[_verdict()])

    _audit(FinalAuditor(llm), canon=canon, arc=arc)
    system = llm.calls[0].system

    assert "no memory of how it was produced" in system
    assert "do NOT score" in system


def test_auditor_may_not_amend_canon_or_invent_bridging_facts(canon, arc):
    """F11/F12: a contradiction 'reconciled' at the last gate has nothing left to catch it."""
    llm = FakeStructuredLLM(responses=[_verdict()])

    _audit(FinalAuditor(llm), canon=canon, arc=arc)
    system = llm.calls[0].system

    assert "may NOT propose a change to canon" in system
    assert "may NOT invent a fact" in system


def test_auditor_passes_an_escalating_verdict_back_intact(canon, arc):
    """The auditor reports the conflict; §6.5 says the caller adjudicates it."""
    escalated = _verdict(decision=Decision.ESCALATE, conflict="canon dates the forgery twice")
    llm = FakeStructuredLLM(responses=[escalated])

    verdict = _audit(FinalAuditor(llm), canon=canon, arc=arc)

    assert verdict.decision is Decision.ESCALATE
    assert verdict.conflict == escalated.conflict
