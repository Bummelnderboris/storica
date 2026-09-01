"""
Tests for consensus sampling (calibration/FINDINGS.md C4).

Measured on the same prompt drawn five times: the chapter with planted contradictions returned
`revise` in 5/5 draws, and the clean control returned a blocking issue in 1/5. The checker is
decisive about real breakage and noisy about clean text, which is what makes *majority* the rule and
*union* a trap — union multiplies the noise it is meant to average out, and sends good chapters into
the repair loop that flattens them.

These tests pin the rule, not the measurement: majority to block, union of issues once blocked.
"""

from __future__ import annotations

import asyncio

from storica.authors import AuthorModel
from storica.canon import Character, Constraints, Premise, Severity, StoryModel
from storica.checkers.base import CheckerIssue, Decision, Verdict
from storica.checkers.consensus import (
    ConsensusProseChecker,
    majority_threshold,
    with_consensus,
)
from storica.checkers.prose_base import ProseChecker
from storica.plan import ChapterSpec, SceneSpec


def _spec() -> ChapterSpec:
    return ChapterSpec(
        chapter=2, title="Die Witwe", purpose="p", pov_character_id="stettler",
        present_character_ids=["stettler"], advances_beats=[], setups=[], payoffs=[],
        promises_made=[], promises_kept=[], entry_state=[], exit_state=[],
        scenes=[SceneSpec(id="s1", location="Stube", character_ids=["stettler"], intent="i", turn="t")],
    )


def _canon() -> StoryModel:
    return StoryModel(
        premise=Premise(), characters={"stettler": Character(canonical_name="Stettler")},
        constraints=Constraints(language="de"),
    )


def _author() -> AuthorModel:
    return AuthorModel(id="d", name="D", language="de", profile={}, question_lines="",
                       nudges="", impression="")


def _issue(ref: str, unit: str, severity=Severity.BLOCKING) -> CheckerIssue:
    return CheckerIssue(unit=unit, kind="coherence", severity=severity, canon_ref=ref, fix_hint="fix")


def _blocking(*refs: str) -> Verdict:
    return Verdict(decision=Decision.REVISE, summary="s",
                   issues=[_issue(r, f"span {r}") for r in refs], conflict="")


def _pass() -> Verdict:
    return Verdict(decision=Decision.PASS, summary="clean", issues=[], conflict="")


class Scripted(ProseChecker):
    """Returns a queued verdict per call, so a flickering reader can be reproduced exactly."""

    name = "canon_consistency"

    def __init__(self, verdicts):
        self.queue = list(verdicts)
        self.calls = 0

    async def check_prose(self, *, prose, canon, spec, author, scene=None, draw=1):
        self.calls += 1
        return self.queue.pop(0)


def _run(checker, scene=None):
    return asyncio.run(checker.check_prose(
        prose="text", canon=_canon(), spec=_spec(), author=_author(), scene=scene,
    ))


# --------------------------------------------------------------------------------------------
# The rule
# --------------------------------------------------------------------------------------------

def test_majority_threshold_is_strict():
    assert majority_threshold(1) == 1
    assert majority_threshold(2) == 2   # a lone dissenter cannot block
    assert majority_threshold(3) == 2
    assert majority_threshold(5) == 3


def test_one_noisy_draw_does_not_block_clean_text():
    """The measured failure mode: 1 of 3 readers flags clean prose. It must not reach repair."""
    inner = Scripted([_blocking("t9"), _pass(), _pass()])
    verdict = _run(ConsensusProseChecker(inner, samples=3))
    assert verdict.decision == Decision.PASS
    assert not verdict.blocking_issues()


def test_the_minority_finding_survives_as_a_warning():
    """Discarding it entirely would throw away a real observation; promoting it would block."""
    inner = Scripted([_blocking("t9"), _pass(), _pass()])
    verdict = _run(ConsensusProseChecker(inner, samples=3))
    assert [i.canon_ref for i in verdict.issues] == ["t9"]
    assert verdict.issues[0].severity == Severity.WARNING


def test_majority_blocks():
    inner = Scripted([_blocking("rutz"), _blocking("rutz"), _pass()])
    verdict = _run(ConsensusProseChecker(inner, samples=3))
    assert verdict.decision == Decision.REVISE
    assert verdict.blocking_issues()


def test_once_blocked_the_issue_list_is_the_union_not_the_intersection():
    """
    A real contradiction spotted by only one careful draw is still real. Having decided the unit is
    broken, repair should see everything anyone found — this is what recovered F12_rutz_split, which
    a single draw missed 1 time in 5.
    """
    inner = Scripted([_blocking("victim"), _blocking("victim", "rutz_split"), _pass()])
    verdict = _run(ConsensusProseChecker(inner, samples=3))
    refs = sorted(i.canon_ref for i in verdict.blocking_issues())
    assert refs == ["rutz_split", "victim"]


def test_the_same_finding_from_two_draws_is_not_double_reported():
    inner = Scripted([_blocking("victim"), _blocking("victim"), _blocking("victim")])
    verdict = _run(ConsensusProseChecker(inner, samples=3))
    assert len(verdict.blocking_issues()) == 1


def test_escalation_also_needs_a_majority():
    """One alarmed reader must not send the run to the adjudicator; that ruling is binding forever."""
    esc = Verdict(decision=Decision.ESCALATE, summary="s", issues=[], conflict="canon disagrees")
    assert _run(ConsensusProseChecker(Scripted([esc, _pass(), _pass()]), samples=3)).decision != Decision.ESCALATE

    got = _run(ConsensusProseChecker(Scripted([esc, esc, _pass()]), samples=3))
    assert got.decision == Decision.ESCALATE
    assert got.conflict == "canon disagrees"


def test_sampling_costs_exactly_k_calls():
    inner = Scripted([_pass(), _pass(), _pass()])
    _run(ConsensusProseChecker(inner, samples=3))
    assert inner.calls == 3


def test_samples_of_one_is_a_pass_through():
    """The opt-out must not change behaviour at all, including not re-wrapping the verdict."""
    original = _blocking("t9")
    inner = Scripted([original])
    got = _run(ConsensusProseChecker(inner, samples=1))
    assert got is original
    assert inner.calls == 1


def test_wrapper_keeps_the_inner_name_so_issue_provenance_is_unchanged():
    assert ConsensusProseChecker(Scripted([]), samples=3).name == "canon_consistency"


# --------------------------------------------------------------------------------------------
# Which checkers get sampled
# --------------------------------------------------------------------------------------------

def test_with_consensus_wraps_only_the_named_checker():
    """Sampling everything would triple the whole gate's cost for asymmetries nobody has measured."""
    class Other(ProseChecker):
        name = "vitality"

        async def check_prose(self, **kw):
            return _pass()

    consistency, vitality = Scripted([]), Other()
    wrapped = with_consensus([consistency, vitality], samples=3)

    assert isinstance(wrapped[0], ConsensusProseChecker)
    assert wrapped[1] is vitality          # untouched
    assert [c.name for c in wrapped] == ["canon_consistency", "vitality"]


def test_default_prose_checkers_samples_consistency_only():
    from storica.llm import FakeStructuredLLM
    from storica.pipeline import default_prose_checkers

    checkers = default_prose_checkers(FakeStructuredLLM(), samples=3)
    sampled = [c.name for c in checkers if isinstance(c, ConsensusProseChecker)]
    assert sampled == ["canon_consistency"]


def test_samples_one_disables_sampling_everywhere():
    from storica.llm import FakeStructuredLLM
    from storica.pipeline import default_prose_checkers

    checkers = default_prose_checkers(FakeStructuredLLM(), samples=1)
    # samples=1 still wraps, but the wrapper is a pass-through; what matters is no extra calls.
    assert all(getattr(c, "samples", 1) == 1 for c in checkers)


# --------------------------------------------------------------------------------------------
# The arithmetic that chose the rule
# --------------------------------------------------------------------------------------------

def test_union_blocking_would_have_been_the_wrong_rule():
    """
    Guards the reasoning, not the implementation. With the measured 20% per-draw false-positive
    rate, union-blocking at k=3 rejects clean text ~49% of the time while majority rejects ~10%.
    If someone 'improves' the rule to union, this states what it costs.
    """
    p = 0.20
    union_k3 = 1 - (1 - p) ** 3
    majority_k3 = 3 * p**2 * (1 - p) + p**3

    assert round(union_k3, 2) == 0.49
    assert round(majority_k3, 2) == 0.10
    assert majority_k3 < p < union_k3   # majority beats even a single draw
