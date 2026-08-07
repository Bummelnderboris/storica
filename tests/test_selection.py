"""
Tests for generate-and-select in prose, and for the vitality checker.

The design claim under test: repair moves prose toward the rubric and therefore away from whatever
was surprising in it, so variance should be spent *choosing* among independent drafts rather than
*sanding down* one. Conception already worked this way; prose did not.

What matters here is the cost shape as much as the behaviour — k drafts must cost k generate calls
plus ONE selection call, not k full checker passes, or selection is unaffordable and gets turned off.
"""

from __future__ import annotations

import asyncio

import pytest

from storica.authors import AuthorModel
from storica.canon import Character, CharacterRole, Constraints, Premise, StoryModel
from storica.checkers.base import CheckerIssue, Decision, Verdict
from storica.checkers.prose_base import ProseChecker
from storica.checkers.vitality import VitalityChecker
from storica.llm import FakeStructuredLLM
from storica.plan import Act, ChapterSpec, MacroArc, SceneSpec, TensionPoint
from storica.stages.prose import CandidateChoice, write_chapter
from storica.trace import Tracer

LIVE = "Er legte den Stift hin. " * 40      # long enough to clear MIN_SCENE_CHARS
DEAD = "Es war sehr traurig und bedeutsam. " * 40
STUB = "zu kurz"


def _canon() -> StoryModel:
    return StoryModel(
        premise=Premise(spark="a spark", central_question="q?", thesis="t"),
        characters={"stettler": Character(canonical_name="Dr. Stettler", role=CharacterRole.PROTAGONIST)},
        constraints=Constraints(language="de"),
    )


def _spec() -> ChapterSpec:
    return ChapterSpec(
        chapter=1, title="Der Totenschein", purpose="establish the certificate",
        pov_character_id="stettler", present_character_ids=["stettler"],
        advances_beats=[], setups=[], payoffs=[], promises_made=[], promises_kept=[],
        entry_state=[], exit_state=[],
        scenes=[SceneSpec(id="s1", location="Praxis", character_ids=["stettler"],
                          intent="show the refusal", turn="he does not sign")],
    )


def _arc() -> MacroArc:
    return MacroArc(
        chapter_count=1, shape="one movement",
        acts=[Act(number=1, title="only", chapters=[1], purpose="all of it")],
        turning_points=[], arc_beats=[], motif_ids=[], promise_ids=[],
        tension_curve=[TensionPoint(chapter=1, tension=5, note="steady")],
    )


def _author() -> AuthorModel:
    return AuthorModel(
        id="duerrenmatt", name="Friedrich Dürrenmatt", language="de", profile={},
        question_lines="", nudges="", impression="dry, procedural, grotesque",
    )


def _write(llm, **kw):
    return asyncio.run(write_chapter(
        spec=_spec(), canon=_canon(), arc=_arc(), author=_author(), llm=llm,
        tracer=Tracer(None), strict=False, **kw,
    ))


# --------------------------------------------------------------------------------------------
# Selection
# --------------------------------------------------------------------------------------------

def test_single_candidate_makes_no_selection_call():
    """The default path must be untouched: one draft, no selector, no extra cost."""
    llm = FakeStructuredLLM(texts=[LIVE, LIVE])
    _write(llm, n_candidates=1)
    assert "CandidateChoice" not in [c.schema for c in llm.calls]


def test_selection_costs_k_generates_and_exactly_one_judgement():
    llm = FakeStructuredLLM(
        texts=[DEAD, LIVE, DEAD, LIVE],  # 3 scene candidates + 1 spare for the chapter pass
        responses=[CandidateChoice(chosen_index=1, reasoning="it surprised me")],
    )
    result = _write(llm, n_candidates=3)

    schemas = [c.schema for c in llm.calls]
    assert schemas.count("<text>") == 3          # k drafts...
    assert schemas.count("CandidateChoice") == 1  # ...and ONE judgement, not k checker passes
    assert LIVE.strip() in result.text            # the selected draft is what survives


def test_the_selected_draft_is_the_one_carried_forward():
    llm = FakeStructuredLLM(
        texts=[DEAD, DEAD, LIVE],
        responses=[CandidateChoice(chosen_index=2, reasoning="the only live one")],
    )
    assert LIVE.strip() in _write(llm, n_candidates=3).text


def test_out_of_range_choice_falls_back_instead_of_crashing():
    """A selector that returns nonsense must not take the book down with it."""
    llm = FakeStructuredLLM(
        texts=[LIVE, DEAD, DEAD],
        responses=[CandidateChoice(chosen_index=99, reasoning="off by a lot")],
    )
    assert LIVE.strip() in _write(llm, n_candidates=3).text  # falls back to the first


def test_stub_candidates_are_dropped_before_selection():
    """Deterministic filtering first: never spend a judgement call comparing against a stub."""
    llm = FakeStructuredLLM(
        texts=[STUB, LIVE, STUB],
        responses=[],  # only one survivor, so no selection call may happen
    )
    result = _write(llm, n_candidates=3)
    assert "CandidateChoice" not in [c.schema for c in llm.calls]
    assert LIVE.strip() in result.text


def test_selection_runs_before_repair_not_after():
    """
    Order is the whole point. If repair ran first we would be sanding one draft and then choosing
    between sanded things; selection has to see the untouched spread.
    """
    calls: list[str] = []

    class Recorder(ProseChecker):
        name = "recorder"

        async def check_prose(self, *, prose, canon, spec, author, scene=None):
            calls.append("check")
            return Verdict(decision=Decision.PASS, summary="fine", issues=[], conflict="")

    llm = FakeStructuredLLM(
        texts=[DEAD, LIVE, DEAD],
        responses=[CandidateChoice(chosen_index=1, reasoning="alive")],
    )
    asyncio.run(write_chapter(
        spec=_spec(), canon=_canon(), arc=_arc(), author=_author(), llm=llm,
        checkers=[Recorder()], tracer=Tracer(None), strict=False, n_candidates=3,
    ))
    selection_index = [c.schema for c in llm.calls].index("CandidateChoice")
    generates_before = [c.schema for c in llm.calls[:selection_index]].count("<text>")
    assert generates_before == 3      # all drafts drawn before anything was judged
    assert calls                       # and checkers did still run, after


# --------------------------------------------------------------------------------------------
# Vitality
# --------------------------------------------------------------------------------------------

def test_vitality_checker_can_block_prose_that_contradicts_nothing():
    """The point of the checker: correct, canon-clean, and still failable."""
    verdict = Verdict(
        decision=Decision.REVISE,
        summary="executes the outline; nothing is imagined",
        issues=[CheckerIssue(
            unit="Es war sehr traurig", kind="meaning", severity="blocking",
            canon_ref="", fix_hint="Cut the sentence; the gesture already carries it.",
        )],
        conflict="",
    )
    llm = FakeStructuredLLM(responses=[verdict])
    got = asyncio.run(VitalityChecker(llm).check_prose(
        prose=DEAD, canon=_canon(), spec=_spec(), author=_author(),
    ))
    assert got.decision == Decision.REVISE
    assert got.blocking_issues()


def test_vitality_prompt_withholds_character_facts_to_keep_it_off_consistency():
    """
    It must not be handed the full canon: given the chance, it will do the easier, more concrete
    job (checking facts) instead of the one it exists for.
    """
    llm = FakeStructuredLLM(
        responses=[Verdict(decision=Decision.PASS, summary="alive", issues=[], conflict="")]
    )
    canon = _canon()
    canon.characters["stettler"].facts = {"profession": "Amtsarzt"}
    asyncio.run(VitalityChecker(llm).check_prose(
        prose=LIVE, canon=canon, spec=_spec(), author=_author(),
    ))
    prompt = llm.calls[0].prompt
    assert "Amtsarzt" not in prompt       # no character facts
    assert "a spark" in prompt            # premise only
    assert "alive" in prompt.lower()      # the rubric it is actually for


def test_vitality_is_told_never_to_escalate():
    """There is no upstream conflict that makes prose dull, so escalation would only launder blame."""
    from storica.checkers.vitality import VITALITY_RUBRIC
    assert "Never escalate" in VITALITY_RUBRIC


def test_vitality_fix_hints_are_subtractive_by_contract():
    """
    The repair loop's contract is minimal edits. That is only safe for vitality if the fixes are
    cuts — 'add tension' would make repair produce longer dead prose.
    """
    from storica.checkers.vitality import SYSTEM, VITALITY_RUBRIC
    assert "never \"add\"" in VITALITY_RUBRIC.lower() or 'never "add"' in VITALITY_RUBRIC
    assert "You never ask for additions." in SYSTEM


def test_vitality_is_in_the_default_prose_checkers():
    from storica.pipeline import default_prose_checkers
    names = [c.name for c in default_prose_checkers(FakeStructuredLLM())]
    assert names == ["canon_consistency", "micro_sense", "voice", "vitality"]
