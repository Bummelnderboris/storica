"""
Tests for the converging repair loop: read once, pin, verify the pins (calibration C7).

Run from the repo root:
    .venv/bin/python -m pytest tests/ -q

The failure these pin down is P6's chapter 1: a scene re-read in full after every repair got a new
set of issues each time — a warning became blocking, a different detail became blocking — and the
budget ran out on a target that never stood still. The contract under test here is that a unit is
read by the gate exactly once, its blocking issues are pinned, and each repair is judged against
the pins alone, so the open list can only shrink or be replaced by damage the repair did.
"""

from __future__ import annotations

import asyncio

import pytest

from storica.canon import Issue, Severity
from storica.checkers import RepairCheck, RepairVerifier, changed_passages
from storica.checkers.base import CheckerIssue
from storica.checkers.verifier import IntroducedProblem, IssueResolution
from storica.llm import FakeStructuredLLM
from storica.stages.prose import ProseGateFailed

from test_prose import (  # noqa: E402 — reuse the prose fixtures rather than copy them
    S1,
    FakeProseChecker,
    _prose,
    _spec,
    _verdict,
    _write,
    author,  # noqa: F401 — pytest fixture
)
from storica.checkers import Decision, Scope, ScopedProseChecker

PINNED = [Issue("micro_sense.micro-sense", Severity.BLOCKING, 'P3: "Am elften März": cut the date', "t1")]

BEFORE = "Erster Absatz bleibt.\n\nAm elften März. Der Name steht dort.\n\nDritter Absatz bleibt."
AFTER = "Erster Absatz bleibt.\n\nDer Name steht dort.\n\nDritter Absatz bleibt."


def _check(*resolved: bool, introduced=()) -> RepairCheck:
    return RepairCheck(
        resolutions=[IssueResolution(index=i + 1, resolved=r, note="n") for i, r in enumerate(resolved)],
        introduced=list(introduced),
    )


def _verify(llm, before=BEFORE, after=AFTER, pinned=PINNED):
    return asyncio.run(RepairVerifier(llm).verify(
        unit="ch01_s1", before=before, after=after, pinned=pinned, canon_block="# Canon slice",
    ))


# --------------------------------------------------------------------------------------------
# The diff the verifier is shown
# --------------------------------------------------------------------------------------------

def test_only_the_changed_paragraph_is_under_review():
    pairs = changed_passages(BEFORE, AFTER)
    assert pairs == [("Am elften März. Der Name steht dort.", "Der Name steht dort.")]


def test_an_unchanged_repair_has_no_passages_and_a_rewrite_has_no_diff():
    assert changed_passages(BEFORE, BEFORE) == []
    rewritten = "Ganz anders.\n\nAuch anders.\n\nVöllig neu."
    assert changed_passages(BEFORE, rewritten) is None


# --------------------------------------------------------------------------------------------
# The verifier's answer
# --------------------------------------------------------------------------------------------

def test_a_resolved_pin_closes():
    llm = FakeStructuredLLM(responses=[_check(True)])
    assert _verify(llm) == []
    prompt = llm.calls[0].prompt
    assert "Am elften März. Der Name steht dort." in prompt           # the before
    assert "Erster Absatz bleibt." not in prompt                      # unchanged text is not shown


def test_an_unresolved_pin_stays_open_verbatim():
    llm = FakeStructuredLLM(responses=[_check(False)])
    assert _verify(llm) == PINNED


def test_damage_the_repair_did_is_blocking():
    damage = IntroducedProblem(unit='"Der Name steht dort."', kind="coherence", canon_ref="",
                               fix_hint="say whose name")
    llm = FakeStructuredLLM(responses=[_check(True, introduced=[damage])])
    still_open = _verify(llm)
    assert len(still_open) == 1
    assert still_open[0].severity is Severity.BLOCKING
    assert "introduced by the repair" in still_open[0].message


def test_a_repair_that_changed_nothing_fixed_nothing_and_costs_no_call():
    llm = FakeStructuredLLM()
    assert _verify(llm, after=BEFORE) == PINNED
    assert llm.calls == []


def test_a_rewrite_is_handed_back_for_a_full_read():
    llm = FakeStructuredLLM()
    assert _verify(llm, after="Ganz anders.\n\nAuch anders.\n\nVöllig neu.") is None
    assert llm.calls == []


# --------------------------------------------------------------------------------------------
# The loop, end to end
# --------------------------------------------------------------------------------------------

def _issue_on(span: str) -> CheckerIssue:
    return CheckerIssue(unit=span, kind="micro-sense", severity=Severity.BLOCKING,
                        canon_ref="", fix_hint=f"cut {span}")


def test_a_reader_that_re_rolls_its_question_can_no_longer_exhaust_the_budget(author):
    """
    The P6 failure, reproduced. Every full read of the scene finds a *different* blocking issue.
    Re-reading after each repair never converges; verifying the pinned issue does, in one round.
    """
    moving_target = FakeProseChecker(
        _verdict(Decision.REVISE, issues=[_issue_on("the dosage")]),
        _verdict(Decision.REVISE, issues=[_issue_on("the hairpin bend")]),
        _verdict(Decision.REVISE, issues=[_issue_on("the eleventh of March")]),
        name="micro_sense",
    )
    draft = "Absatz eins.\n\nDie Dosis, die er verordnet hatte.\n\n" + _prose("Absatz drei")
    repaired = "Absatz eins.\n\nEr hatte sich geirrt.\n\n" + _prose("Absatz drei")
    llm = FakeStructuredLLM(texts=[draft, repaired], responses=[_check(True)])
    verifier = RepairVerifier(llm)
    # scene-scoped, as the shipped gate scopes micro-sense: the assembled chapter is not re-rolled
    scoped = ScopedProseChecker(moving_target, Scope.SCENE)

    result = _write(llm, author, spec=_spec(scenes=[S1]), checkers=[scoped],
                    verifier=verifier, max_repairs=2)

    assert result.is_valid and result.repairs == 1
    assert moving_target.units == ["s1"]         # read in full exactly once


def test_without_a_verifier_the_same_reader_exhausts_the_budget(author):
    """The control for the test above: the old loop re-reads and chases the new question."""
    moving_target = FakeProseChecker(
        _verdict(Decision.REVISE, issues=[_issue_on("the dosage")]),
        _verdict(Decision.REVISE, issues=[_issue_on("the hairpin bend")]),
        _verdict(Decision.REVISE, issues=[_issue_on("the eleventh of March")]),
        name="micro_sense",
    )
    llm = FakeStructuredLLM(texts=[_prose(str(i)) for i in range(3)])

    with pytest.raises(ProseGateFailed):
        _write(llm, author, spec=_spec(scenes=[S1]), checkers=[moving_target], max_repairs=2)


def test_warnings_from_the_one_full_read_survive_to_the_result(author):
    reader = FakeProseChecker(
        _verdict(Decision.REVISE, issues=[
            _issue_on("the dosage"),
            CheckerIssue(unit="slack transition", kind="micro-sense", severity=Severity.WARNING,
                         canon_ref="", fix_hint="tighten"),
        ]),
        name="micro_sense",
    )
    draft = "Absatz eins.\n\nDie Dosis.\n\n" + _prose("drei")
    repaired = "Absatz eins.\n\nDer Irrtum.\n\n" + _prose("drei")
    llm = FakeStructuredLLM(texts=[draft, repaired], responses=[_check(True)])

    result = _write(llm, author, spec=_spec(scenes=[S1]), checkers=[reader],
                    verifier=RepairVerifier(llm))

    assert result.is_valid
    assert any("slack transition" in i.message for i in result.issues)


def test_a_repair_that_rewrites_the_scene_is_read_in_full_again(author):
    reader = FakeProseChecker(_verdict(Decision.REVISE, issues=[_issue_on("x")]), name="micro_sense")
    draft = "Eins.\n\nZwei.\n\n" + _prose("drei")
    rewrite = "Ganz neu.\n\nAnders.\n\n" + _prose("vier")
    llm = FakeStructuredLLM(texts=[draft, rewrite])

    result = _write(llm, author, spec=_spec(scenes=[S1]), checkers=[reader],
                    verifier=RepairVerifier(llm))

    assert result.is_valid
    assert reader.units == ["s1", "s1", None]    # the rewrite was genuinely new text, so re-read


def test_readers_skipped_by_the_short_circuit_read_the_repaired_text(author):
    """
    Found live in P6 (ch2 s1): canon-consistency blocked, the short-circuit skipped the other
    readers "to read the repaired text instead", the verifier cleared the pins — and nothing ever
    made the others read. The scene would have passed unread by micro-sense, voice and vitality.
    """
    canon_reader = FakeProseChecker(
        _verdict(Decision.REVISE, issues=[_issue_on("the wrong office")]), name="canon_consistency")
    micro = FakeProseChecker(name="micro_sense")
    draft = "Absatz eins.\n\nDer Notar unterschrieb.\n\n" + _prose("drei")
    repaired = "Absatz eins.\n\nDer Amtsarzt unterschrieb.\n\n" + _prose("drei")
    llm = FakeStructuredLLM(texts=[draft, repaired], responses=[_check(True)])
    scoped = [ScopedProseChecker(canon_reader, Scope.SCENE), ScopedProseChecker(micro, Scope.SCENE)]

    result = _write(llm, author, spec=_spec(scenes=[S1]), checkers=scoped,
                    verifier=RepairVerifier(llm))

    assert result.is_valid and result.repairs == 1
    assert canon_reader.units == ["s1"]              # read once; the fix was verified, not re-read
    assert micro.units == ["s1"]                     # ... and micro-sense did read the scene
    assert micro.prose == [repaired]                 # — the repaired text, as the short-circuit promises


def test_what_the_skipped_readers_find_is_pinned_and_repaired_too(author):
    canon_reader = FakeProseChecker(
        _verdict(Decision.REVISE, issues=[_issue_on("the wrong office")]), name="canon_consistency")
    micro = FakeProseChecker(
        _verdict(Decision.REVISE, issues=[_issue_on("Die Spannung wuchs")]), name="micro_sense")
    t1 = "Eins.\n\nDer Notar unterschrieb.\n\nDie Spannung wuchs.\n\n" + _prose("vier")
    t2 = "Eins.\n\nDer Amtsarzt unterschrieb.\n\nDie Spannung wuchs.\n\n" + _prose("vier")
    t3 = "Eins.\n\nDer Amtsarzt unterschrieb.\n\nEr legte die Feder hin.\n\n" + _prose("vier")
    llm = FakeStructuredLLM(texts=[t1, t2, t3], responses=[_check(True), _check(True)])
    scoped = [ScopedProseChecker(canon_reader, Scope.SCENE), ScopedProseChecker(micro, Scope.SCENE)]

    result = _write(llm, author, spec=_spec(scenes=[S1]), checkers=scoped,
                    verifier=RepairVerifier(llm), max_repairs=3)

    assert result.is_valid and result.repairs == 2
    assert micro.prose == [t2]                       # read once, after the first repair
