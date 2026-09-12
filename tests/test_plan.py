"""
Tests for P3: the macro arc, just-in-time chapter specs, the meaning ledger, and the Intent checker.

Run from the repo root:
    .venv/bin/python -m pytest tests/ -q

Offline: every LLM call is served by `FakeStructuredLLM`, so what is under test is the plan
contract — does the deterministic gate catch drift between plan and canon, does the cheap checker
run before the expensive one, does a checker verdict drive repair, does an escalation stop the run.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from storica.authors import load_author
from storica.brief import Brief, save_brief
from storica.canon import (
    Character,
    CharacterArc,
    CharacterRole,
    Constraints,
    Motif,
    MotifStatus,
    Premise,
    PromiseStatus,
    Relationship,
    StoryModel,
    TimelineEvent,
    blocking,
    canon_slice,
    load_canon,
    save_canon,
)
from storica.checkers import Decision, Escalation, IntentChecker, Verdict
from storica.checkers.base import CheckerIssue
from storica.canon.validation import Severity
from storica.llm import FakeStructuredLLM
from storica.pipeline import plan_macro_arc, spec_chapter
from storica.plan import (
    Act,
    ArcBeat,
    ChapterSpec,
    MacroArcDraft,
    MotifDraft,
    PromiseDraft,
    SceneSpec,
    StateFact,
    TensionPoint,
    TurningPoint,
    load_chapter_spec,
    load_macro_arc,
    save_chapter_spec,
    save_macro_arc,
    specced_chapters,
    validate_chapter_spec,
    validate_continuity,
    validate_macro_arc_draft,
)
from storica.stages import (
    ChapterSpecGateFailed,
    MacroArcGateFailed,
    build_chapter_spec,
    build_macro_arc,
    promote_ledger,
    to_macro_arc,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
AUTHORS_ROOT = REPO_ROOT / "authors"


# --------------------------------------------------------------------------------------------
# Builders
# --------------------------------------------------------------------------------------------

def _canon(chapter_count: int = 3) -> StoryModel:
    return StoryModel(
        premise=Premise(spark="a body in the gorge", central_question="can he resist?", thesis="guilt administered",
                        why_this_author="chance vs plan"),
        author_id="duerrenmatt",
        characters={
            "stettler": Character(
                canonical_name="Dr. Konrad Stettler",
                aliases=["Stettler", "der Amtsarzt"],
                role=CharacterRole.PROTAGONIST,
                facts={"profession": "Amtsarzt"},
                arc=CharacterArc(want="close the case", need="confess", flaw="order", trajectory="hardens"),
            ),
            "rutz": Character(
                canonical_name="Pfarrer Johannes Rutz",
                aliases=["Rutz"],
                role=CharacterRole.ANTAGONIST,
                facts={"office": "village priest"},
            ),
        },
        relationships=[Relationship(a="stettler", b="rutz", type="debtor_of")],
        world_facts={"setting": "Lauenegg"},
        timeline=[TimelineEvent(id="t1", when="20y prior", event="the forgery", involves=["stettler"], order=1)],
        constraints=Constraints(language="de", forbidden=["justice triumphs"], chapter_count=chapter_count),
    )


def _arc_draft(**over) -> MacroArcDraft:
    base = dict(
        chapter_count=3,
        shape="A man who files his guilt is handed the chance to close the file for good.",
        acts=[
            Act(number=1, title="The body", chapters=[1, 2], purpose="the chance is offered"),
            Act(number=2, title="The signature", chapters=[3], purpose="he takes it and is closed in"),
        ],
        turning_points=[TurningPoint(id="tp1", chapter=3, description="he signs", reverses="that he could still confess")],
        arc_beats=[
            ArcBeat(id="b1", character_id="stettler", chapter=1, beat="is handed the certificate", advances="want"),
            ArcBeat(id="b2", character_id="rutz", chapter=3, beat="stops asking", advances="trajectory"),
        ],
        motifs=[MotifDraft(id="formula_echo", desc="the same phrase recurs", setup_ch=1, payoff_ch=3)],
        promises=[PromiseDraft(id="berta_question", desc="the unanswered question", made_ch=1, kept_ch=3)],
        tension_curve=[
            TensionPoint(chapter=1, tension=3, note="the offer"),
            TensionPoint(chapter=2, tension=6, note="the doubt"),
            TensionPoint(chapter=3, tension=9, note="the signature"),
        ],
    )
    base.update(over)
    return MacroArcDraft(**base)


def _spec(chapter: int = 1, **over) -> ChapterSpec:
    base = dict(
        chapter=chapter,
        title="Das Protokoll",
        purpose="Stettler is handed the one case he cannot file honestly.",
        pov_character_id="stettler",
        present_character_ids=["stettler", "rutz"],
        advances_beats=["b1"],
        setups=["formula_echo"],
        payoffs=[],
        promises_made=["berta_question"],
        promises_kept=[],
        entry_state=[],
        exit_state=[StateFact(key="body:location", value="in the gorge, unexamined")],
        scenes=[
            SceneSpec(
                id="s1",
                location="setting",
                character_ids=["stettler"],
                intent="carries b1: the certificate reaches him",
                turn="he realises whose signature is required",
            )
        ],
    )
    base.update(over)
    return ChapterSpec(**base)


def _verdict(decision=Decision.PASS, issues=None, conflict="") -> Verdict:
    return Verdict(decision=decision, summary="judged", issues=issues or [], conflict=conflict)


def _blocking_issue(unit="ch01") -> CheckerIssue:
    return CheckerIssue(
        unit=unit, kind="meaning", severity=Severity.BLOCKING,
        canon_ref="b1", fix_hint="give chapter 2 a beat or cut it",
    )


@pytest.fixture
def author():
    return load_author("duerrenmatt", AUTHORS_ROOT)


@pytest.fixture
def brief() -> Brief:
    return Brief(author_id="duerrenmatt", spark="a death certificate", language="de", chapter_count=3)


# --------------------------------------------------------------------------------------------
# Canon slice — the grounding payload
# --------------------------------------------------------------------------------------------

def test_canon_slice_carries_full_truth_for_the_ids_it_is_given():
    canon = promote_ledger(_canon(), _arc_draft())
    text = canon_slice(canon, character_ids=["stettler"], motif_ids=["formula_echo"])

    assert "Dr. Konrad Stettler" in text and "der Amtsarzt" in text     # aliases travel with the id
    assert "profession: Amtsarzt" in text
    assert "want: close the case" in text                                # arc travels too
    assert "formula_echo" in text
    assert "justice triumphs" in text                                    # constraints are grounding
    assert "Pfarrer Johannes Rutz" not in text                           # not asked for


def test_canon_slice_flags_unknown_ids_instead_of_dropping_them():
    text = canon_slice(_canon(), character_ids=["stettler", "ghost"])
    assert "!! NOT IN CANON" in text and "ghost" in text


# --------------------------------------------------------------------------------------------
# Stage 3 — deterministic arc validation
# --------------------------------------------------------------------------------------------

def _codes(issues):
    return {i.code for i in issues}


def test_clean_arc_validates():
    assert blocking(validate_macro_arc_draft(_arc_draft(), _canon())) == []


def test_acts_must_partition_the_chapters():
    gap = _arc_draft(acts=[Act(number=1, title="a", chapters=[1, 2], purpose="p")])
    assert "arc.act_gap" in _codes(blocking(validate_macro_arc_draft(gap, _canon())))

    overlap = _arc_draft(acts=[
        Act(number=1, title="a", chapters=[1, 2], purpose="p"),
        Act(number=2, title="b", chapters=[2, 3], purpose="p"),
    ])
    assert "arc.act_overlap" in _codes(blocking(validate_macro_arc_draft(overlap, _canon())))


def test_beat_against_unknown_character_is_blocking():
    draft = _arc_draft(arc_beats=[ArcBeat(id="b1", character_id="ghost", chapter=1, beat="x", advances="want")])
    assert "arc.beat_character" in _codes(blocking(validate_macro_arc_draft(draft, _canon())))


def test_chapter_count_must_match_canon():
    draft = _arc_draft(chapter_count=4)
    assert "arc.chapter_count" in _codes(blocking(validate_macro_arc_draft(draft, _canon(3))))


def test_tension_curve_must_cover_every_chapter():
    draft = _arc_draft(tension_curve=[TensionPoint(chapter=1, tension=3, note="x")])
    assert "arc.tension_gap" in _codes(blocking(validate_macro_arc_draft(draft, _canon())))


def test_ledger_ordering_is_enforced():
    motif = _arc_draft(motifs=[MotifDraft(id="m1", desc="d", setup_ch=3, payoff_ch=1)])
    assert "arc.motif_payoff_before_setup" in _codes(blocking(validate_macro_arc_draft(motif, _canon())))

    promise = _arc_draft(promises=[PromiseDraft(id="p1", desc="d", made_ch=3, kept_ch=1)])
    assert "arc.promise_kept_before_made" in _codes(blocking(validate_macro_arc_draft(promise, _canon())))


def test_unkept_promise_is_a_warning_not_a_failure():
    """Deliberate non-resolution is allowed — but it must be visible as a decision."""
    draft = _arc_draft(promises=[PromiseDraft(id="p1", desc="d", made_ch=1, kept_ch=0)])
    issues = validate_macro_arc_draft(draft, _canon())
    assert "arc.promise_unkept" in _codes(issues)
    assert blocking(issues) == []


def test_character_without_a_beat_is_a_warning():
    draft = _arc_draft(arc_beats=[
        ArcBeat(id="b1", character_id="stettler", chapter=1, beat="x", advances="want")
    ])
    issues = validate_macro_arc_draft(draft, _canon())
    assert "arc.character_no_beat" in _codes(issues)   # rutz is the antagonist and carries nothing
    assert blocking(issues) == []


# --------------------------------------------------------------------------------------------
# Stage 3 — ledger promotion + stage run
# --------------------------------------------------------------------------------------------

def test_promote_ledger_writes_the_schedule_into_canon():
    canon = promote_ledger(_canon(), _arc_draft())
    assert canon.motifs == [Motif(id="formula_echo", desc="the same phrase recurs", setup_ch=1,
                                 payoff_ch=3, status=MotifStatus.PLANNED)]
    assert canon.promises[0].status == PromiseStatus.OPEN
    assert canon.promises[0].kept_ch == 3


def test_promote_ledger_maps_unkept_promise_to_none():
    canon = promote_ledger(_canon(), _arc_draft(promises=[PromiseDraft(id="p1", desc="d", made_ch=1, kept_ch=0)]))
    assert canon.promises[0].kept_ch is None


def test_stored_arc_references_the_ledger_by_id_only():
    """The arc must not restate motif text — a restatement is a second source of truth."""
    arc = to_macro_arc(_arc_draft())
    assert arc.motif_ids == ["formula_echo"] and arc.promise_ids == ["berta_question"]
    assert "the same phrase recurs" not in arc.model_dump_json()


def test_build_macro_arc_clean_path(brief, author):
    llm = FakeStructuredLLM(responses=[_arc_draft()])
    result = asyncio.run(build_macro_arc(canon=_canon(), brief=brief, author=author, llm=llm))

    assert result.is_valid and result.repairs == 0
    assert result.arc.beats_for(1)[0].id == "b1"
    assert result.arc.act_for(3).number == 2
    assert [m.id for m in result.canon.motifs] == ["formula_echo"]


def test_build_macro_arc_repairs_a_broken_arc(brief, author):
    broken = _arc_draft(acts=[Act(number=1, title="a", chapters=[1], purpose="p")])  # chapters 2,3 orphaned
    llm = FakeStructuredLLM(responses=[broken, _arc_draft()])

    result = asyncio.run(build_macro_arc(canon=_canon(), brief=brief, author=author, llm=llm))

    assert result.repairs == 1 and result.is_valid
    assert "arc.act_gap" in llm.calls[1].prompt


def test_build_macro_arc_raises_when_budget_spent(brief, author):
    broken = _arc_draft(tension_curve=[TensionPoint(chapter=1, tension=3, note="x")])
    llm = FakeStructuredLLM(responses=[broken, broken, broken])

    with pytest.raises(MacroArcGateFailed) as exc:
        asyncio.run(build_macro_arc(canon=_canon(), brief=brief, author=author, llm=llm, max_repairs=2))

    assert any(i.code == "arc.tension_gap" for i in exc.value.issues)
    assert len(llm.calls) == 3


# --------------------------------------------------------------------------------------------
# The Intent checker
# --------------------------------------------------------------------------------------------

def test_intent_checker_runs_only_after_the_cheap_gate_passes(brief, author):
    """Never spend an LLM checker call on a structurally broken unit (the F3 cost reclaim)."""
    broken = _arc_draft(tension_curve=[TensionPoint(chapter=1, tension=3, note="x")])
    llm = FakeStructuredLLM(responses=[broken, _arc_draft(), _verdict()])

    result = asyncio.run(build_macro_arc(
        canon=_canon(), brief=brief, author=author, llm=llm,
        intent_checker=IntentChecker(llm),
    ))

    assert result.is_valid and result.repairs == 1
    # draft (broken) -> repair -> verdict: exactly one checker call, and only after the repair
    assert [c.schema for c in llm.calls] == ["MacroArcDraft", "MacroArcDraft", "Verdict"]


def test_intent_blocking_issue_drives_a_repair(brief, author):
    llm = FakeStructuredLLM(responses=[
        _arc_draft(),
        _verdict(Decision.REVISE, issues=[_blocking_issue("chapter 2")]),
        _arc_draft(),
        _verdict(),
    ])

    result = asyncio.run(build_macro_arc(
        canon=_canon(), brief=brief, author=author, llm=llm, intent_checker=IntentChecker(llm),
    ))

    assert result.repairs == 1 and result.is_valid
    # the repair agent is told the checker's finding verbatim, grounded in the canon ref
    assert "give chapter 2 a beat or cut it" in llm.calls[2].prompt


def test_intent_warning_does_not_spin_the_loop(brief, author):
    warning = CheckerIssue(unit="ch2", kind="meaning", severity=Severity.WARNING,
                           canon_ref="", fix_hint="could be tighter")
    llm = FakeStructuredLLM(responses=[_arc_draft(), _verdict(Decision.REVISE, issues=[warning])])

    result = asyncio.run(build_macro_arc(
        canon=_canon(), brief=brief, author=author, llm=llm, intent_checker=IntentChecker(llm),
    ))

    assert result.repairs == 0 and result.is_valid
    assert any(i.code == "intent.meaning" for i in result.issues)


def test_escalation_stops_the_run_instead_of_papering_over_it(brief, author):
    llm = FakeStructuredLLM(responses=[
        _arc_draft(),
        _verdict(Decision.ESCALATE, conflict="the canon says Rutz is dead before his beat"),
    ])

    with pytest.raises(Escalation) as exc:
        asyncio.run(build_macro_arc(
            canon=_canon(), brief=brief, author=author, llm=llm, intent_checker=IntentChecker(llm),
        ))

    assert "Rutz is dead" in exc.value.conflict
    assert exc.value.unit == "macro_arc"


def test_intent_checker_prompt_is_grounded_in_canon_and_the_assignment(brief, author):
    llm = FakeStructuredLLM(responses=[_arc_draft(), _verdict()])
    asyncio.run(build_macro_arc(
        canon=_canon(), brief=brief, author=author, llm=llm, intent_checker=IntentChecker(llm),
    ))

    prompt = llm.calls[1].prompt
    assert "Canon slice (SOURCE OF TRUTH" in prompt
    assert "Unit under review: the macro arc" in prompt
    assert "Does every chapter do work?" in prompt        # the rubric, not a score
    assert "Die Unmöglichkeit der Gerechtigkeit" in prompt  # judged by THIS author's obsessions


# --------------------------------------------------------------------------------------------
# Stage 4 — chapter spec validation
# --------------------------------------------------------------------------------------------

def _planned():
    canon = promote_ledger(_canon(), _arc_draft())
    return canon, to_macro_arc(_arc_draft())


def test_clean_spec_validates():
    canon, arc = _planned()
    assert blocking(validate_chapter_spec(_spec(1), canon, arc)) == []


def test_dropping_an_assigned_beat_is_blocking():
    canon, arc = _planned()
    issues = validate_chapter_spec(_spec(1, advances_beats=[]), canon, arc)
    assert "spec.beat_dropped" in _codes(blocking(issues))


def test_stealing_another_chapters_beat_is_blocking():
    canon, arc = _planned()
    issues = validate_chapter_spec(_spec(1, advances_beats=["b1", "b2"]), canon, arc)
    assert "spec.beat_misplaced" in _codes(blocking(issues))


def test_dropping_a_scheduled_ledger_event_is_blocking():
    canon, arc = _planned()
    issues = validate_chapter_spec(_spec(1, setups=[], promises_made=[]), canon, arc)
    assert {"spec.motif_dropped", "spec.promise_dropped"} <= _codes(blocking(issues))


def test_pov_must_be_present_and_known():
    canon, arc = _planned()
    assert "spec.pov_absent" in _codes(blocking(
        validate_chapter_spec(_spec(1, pov_character_id="rutz", present_character_ids=["stettler"],
                                    scenes=[SceneSpec(id="s1", location="l", character_ids=["stettler"],
                                                      intent="i", turn="t")]), canon, arc)))
    assert "spec.pov" in _codes(blocking(
        validate_chapter_spec(_spec(1, pov_character_id="ghost"), canon, arc)))


def test_scene_cast_must_come_from_the_chapter_cast():
    canon, arc = _planned()
    spec = _spec(1, scenes=[SceneSpec(id="s1", location="l", character_ids=["ghost"], intent="i", turn="t")])
    assert "spec.scene_cast" in _codes(blocking(validate_chapter_spec(spec, canon, arc)))


def test_a_scene_that_changes_nothing_is_blocking():
    canon, arc = _planned()
    spec = _spec(1, scenes=[SceneSpec(id="s1", location="l", character_ids=["stettler"], intent="i", turn="  ")])
    assert "spec.scene_no_turn" in _codes(blocking(validate_chapter_spec(spec, canon, arc)))


def test_a_chapter_without_a_purpose_is_blocking():
    canon, arc = _planned()
    assert "spec.no_purpose" in _codes(blocking(validate_chapter_spec(_spec(1, purpose=""), canon, arc)))


def test_continuity_gap_is_a_warning():
    previous = _spec(1)
    current = _spec(2, advances_beats=[], setups=[], promises_made=[], entry_state=[])
    issues = validate_continuity(current, previous)
    assert [i.code for i in issues] == ["spec.continuity_gap"]
    assert blocking(issues) == []


# --------------------------------------------------------------------------------------------
# Stage 4 — the stage itself
# --------------------------------------------------------------------------------------------

def test_build_chapter_spec_clean_path(author):
    canon, arc = _planned()
    llm = FakeStructuredLLM(responses=[_spec(1)])

    result = asyncio.run(build_chapter_spec(chapter=1, canon=canon, arc=arc, author=author, llm=llm))

    assert result.is_valid and result.repairs == 0
    assert result.spec.advances_beats == ["b1"]


def test_build_chapter_spec_prompt_carries_the_assignment_and_full_canon(author):
    canon, arc = _planned()
    llm = FakeStructuredLLM(responses=[_spec(1)])
    asyncio.run(build_chapter_spec(chapter=1, canon=canon, arc=arc, author=author, llm=llm))

    prompt = llm.calls[0].prompt
    assert "Canon slice (SOURCE OF TRUTH" in prompt
    assert "[b1] stettler: is handed the certificate" in prompt   # assigned beats, by id
    assert "[formula_echo] plant:" in prompt
    assert "[berta_question] make:" in prompt
    assert "Steer AWAY" in prompt                                  # the author's voice nudges


def test_build_chapter_spec_repairs_a_dropped_beat(author):
    canon, arc = _planned()
    llm = FakeStructuredLLM(responses=[_spec(1, advances_beats=[]), _spec(1)])

    result = asyncio.run(build_chapter_spec(chapter=1, canon=canon, arc=arc, author=author, llm=llm))

    assert result.repairs == 1 and result.is_valid
    assert "spec.beat_dropped" in llm.calls[1].prompt


def test_build_chapter_spec_rejects_a_spec_for_the_wrong_chapter(author):
    canon, arc = _planned()
    llm = FakeStructuredLLM(responses=[_spec(3), _spec(3), _spec(3)])

    with pytest.raises(ChapterSpecGateFailed) as exc:
        asyncio.run(build_chapter_spec(chapter=1, canon=canon, arc=arc, author=author, llm=llm, max_repairs=2))

    assert any(i.code == "spec.wrong_chapter" for i in exc.value.issues)


def test_chapter_spec_intent_check_runs_and_can_pass(author):
    canon, arc = _planned()
    llm = FakeStructuredLLM(responses=[_spec(1), _verdict()])

    result = asyncio.run(build_chapter_spec(
        chapter=1, canon=canon, arc=arc, author=author, llm=llm, intent_checker=IntentChecker(llm),
    ))

    assert result.is_valid
    assert [c.schema for c in llm.calls] == ["ChapterSpec", "Verdict"]
    assert "Unit under review: chapter 1 spec" in llm.calls[1].prompt


# --------------------------------------------------------------------------------------------
# Plan store
# --------------------------------------------------------------------------------------------

def test_plan_store_roundtrips(tmp_path):
    arc = to_macro_arc(_arc_draft())
    save_macro_arc(arc, tmp_path)
    assert load_macro_arc(tmp_path) == arc

    save_chapter_spec(_spec(1), tmp_path)
    save_chapter_spec(_spec(3, advances_beats=["b2"], setups=[], payoffs=["formula_echo"],
                            promises_made=[], promises_kept=["berta_question"]), tmp_path)
    assert specced_chapters(tmp_path) == [1, 3]
    assert load_chapter_spec(tmp_path, 1).title == "Das Protokoll"
    assert (tmp_path / "chapters" / "ch01.spec.json").exists()


# --------------------------------------------------------------------------------------------
# Pipeline wiring
# --------------------------------------------------------------------------------------------

def _novel(tmp_path, brief) -> Path:
    novel = tmp_path / "novel"
    save_brief(brief, novel / "00_input")
    save_canon(_canon(), novel / "01_canon")
    return novel


def test_plan_macro_arc_commits_the_ledger_into_canon(tmp_path, brief):
    novel = _novel(tmp_path, brief)
    llm = FakeStructuredLLM(responses=[_arc_draft(), _verdict()])

    arc = asyncio.run(plan_macro_arc(novel_dir=novel, authors_root=AUTHORS_ROOT, llm=llm))

    assert load_macro_arc(novel / "02_plan") == arc
    canon = load_canon(novel / "01_canon")
    assert canon.version == 2                                    # the ledger's arrival is a canon change
    assert [m.id for m in canon.motifs] == ["formula_echo"]
    assert (novel / "01_canon" / "history" / "v0002.json").exists()
    # both the planning call and the checker call are on disk
    traced = sorted(p.name for p in (novel / "04_trace").glob("*.json"))
    assert traced == ["001_macro_arc.json", "002_intent_check_macro_arc.json"]


def test_spec_chapter_writes_the_spec_and_chains_continuity(tmp_path, brief):
    novel = _novel(tmp_path, brief)
    llm = FakeStructuredLLM(responses=[_arc_draft(), _verdict()])
    asyncio.run(plan_macro_arc(novel_dir=novel, authors_root=AUTHORS_ROOT, llm=llm))

    llm.responses.append(_spec(1))
    spec1 = asyncio.run(spec_chapter(novel_dir=novel, authors_root=AUTHORS_ROOT, chapter=1,
                                     llm=llm, check_intent=False))
    assert load_chapter_spec(novel / "02_plan", 1) == spec1

    # chapter 2 is elaborated only now, and sees chapter 1's exit state
    ch2 = _spec(2, advances_beats=[], setups=[], promises_made=[],
                entry_state=[StateFact(key="body:location", value="in the gorge, unexamined")],
                exit_state=[StateFact(key="stettler:knows", value="that Rutz saw the file")])
    llm.responses.append(ch2)
    spec2 = asyncio.run(spec_chapter(novel_dir=novel, authors_root=AUTHORS_ROOT, chapter=2,
                                     llm=llm, check_intent=False))

    assert spec2.chapter == 2 and specced_chapters(novel / "02_plan") == [1, 2]
    assert "body:location: in the gorge, unexamined" in llm.calls[-1].prompt  # previous exit state carried in


def test_spec_chapter_persists_a_readable_artifact(tmp_path, brief):
    novel = _novel(tmp_path, brief)
    llm = FakeStructuredLLM(responses=[_arc_draft(), _verdict(), _spec(1)])
    asyncio.run(plan_macro_arc(novel_dir=novel, authors_root=AUTHORS_ROOT, llm=llm))
    asyncio.run(spec_chapter(novel_dir=novel, authors_root=AUTHORS_ROOT, chapter=1,
                             llm=llm, check_intent=False))

    on_disk = json.loads((novel / "02_plan" / "chapters" / "ch01.spec.json").read_text())
    assert on_disk["advances_beats"] == ["b1"]
    assert on_disk["scenes"][0]["turn"]
