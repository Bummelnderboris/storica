"""
The gate as policy: which lens fires where, and what it may do about what it finds.

These are tests about *wiring*, not judgement. A lens is the questions a reader asks; the registry
decides which units it reads (the trigger) and whether its findings advise, block, or reach the
adjudicator (the authority). Those three used to be welded together inside each checker class,
which is why a reader could only ever be used at the seam it was written for.
"""

from __future__ import annotations

import asyncio
from typing import List, Optional

from storica.authors import AuthorModel
from storica.canon import (
    Character,
    CharacterRole,
    Constraints,
    Premise,
    Severity,
    StoryModel,
)
from storica.checkers import Authority, Scope, build_prose_gate
from storica.checkers.base import CheckerIssue, Decision, Verdict
from storica.checkers.registry import PROSE_GATE, BoundedProseChecker, ScopedProseChecker
from storica.llm import FakeStructuredLLM
from storica.plan import ChapterSpec, SceneSpec, StateFact

SCENE = SceneSpec(id="s1", location="Pfarrhaus", character_ids=["stettler"],
                  intent="the certificate reaches him", turn="he sees whose signature is required")


def _canon() -> StoryModel:
    return StoryModel(
        premise=Premise(spark="a body in the gorge"),
        author_id="duerrenmatt",
        characters={"stettler": Character(canonical_name="Dr. Konrad Stettler",
                                          role=CharacterRole.PROTAGONIST)},
        constraints=Constraints(language="de"),
    )


def _spec() -> ChapterSpec:
    return ChapterSpec(
        chapter=1, title="Das Protokoll", purpose="he is handed the case he cannot file honestly",
        pov_character_id="stettler", present_character_ids=["stettler"],
        advances_beats=[], setups=[], payoffs=[], promises_made=[], promises_kept=[],
        entry_state=[], exit_state=[StateFact(key="body:location", value="im Chrachen")],
        scenes=[SCENE],
    )


def _author() -> AuthorModel:
    return AuthorModel(id="duerrenmatt", name="Friedrich Dürrenmatt", language="de", profile={},
                       question_lines="", nudges="", impression="")


def _issue(severity=Severity.BLOCKING) -> CheckerIssue:
    return CheckerIssue(unit="s1", kind="intent", severity=severity, canon_ref="b1",
                        fix_hint="the beat never lands")


def _verdict(decision=Decision.REVISE, issues=None, conflict="") -> Verdict:
    return Verdict(decision=decision, summary="judged", issues=issues or [], conflict=conflict)


class Recording:
    """A lens that records what it was asked to read and answers from a queue."""

    def __init__(self, *verdicts: Verdict, name: str = "recorder"):
        self.name = name
        self.verdicts = list(verdicts)
        self.seen: List[Optional[str]] = []

    async def check_prose(self, *, prose, canon, spec, author, scene=None, draw: int = 1) -> Verdict:
        self.seen.append(scene.id if scene is not None else None)
        return self.verdicts.pop(0) if self.verdicts else _verdict(Decision.PASS)


def _run(reader, *, scene=None) -> Verdict:
    return asyncio.run(reader.check_prose(prose="Er unterschrieb nicht.", canon=_canon(),
                                          spec=_spec(), author=_author(), scene=scene))


# --------------------------------------------------------------------------------------------
# The trigger
# --------------------------------------------------------------------------------------------

def test_a_chapter_scoped_lens_does_not_read_scenes_and_costs_nothing_to_skip():
    inner = Recording()
    reader = ScopedProseChecker(inner, Scope.CHAPTER)

    verdict = _run(reader, scene=SCENE)

    assert verdict.decision == Decision.PASS and verdict.issues == []
    assert inner.seen == [], "an out-of-scope unit must not reach the model at all"


def test_a_chapter_scoped_lens_reads_the_assembled_chapter():
    inner = Recording(_verdict(issues=[_issue()]))
    reader = ScopedProseChecker(inner, Scope.CHAPTER)

    verdict = _run(reader, scene=None)

    assert inner.seen == [None] and verdict.blocking_issues()


def test_a_scene_scoped_lens_is_the_mirror_image():
    inner = Recording()
    reader = ScopedProseChecker(inner, Scope.SCENE)

    _run(reader, scene=SCENE)
    _run(reader, scene=None)

    assert inner.seen == ["s1"]


def test_the_wrapper_keeps_the_lens_name_so_the_gate_can_still_recognise_it():
    """The prose loop short-circuits on `canon_consistency` by name; wrapping must be invisible."""
    assert ScopedProseChecker(Recording(name="canon_consistency"), Scope.CHAPTER).name == "canon_consistency"
    assert BoundedProseChecker(Recording(name="canon_consistency"), Authority.ADVISE).name == "canon_consistency"


# --------------------------------------------------------------------------------------------
# The authority
# --------------------------------------------------------------------------------------------

def test_an_advisory_lens_records_its_findings_as_warnings_and_never_blocks():
    reader = BoundedProseChecker(Recording(_verdict(issues=[_issue()])), Authority.ADVISE)

    verdict = _run(reader)

    assert verdict.decision == Decision.PASS
    assert verdict.blocking_issues() == []
    assert [i.severity for i in verdict.issues] == [Severity.WARNING]
    assert verdict.issues[0].fix_hint == "the beat never lands", "the finding itself is kept"


def test_an_advisory_lens_cannot_escalate_but_its_conflict_survives_as_a_warning():
    reader = BoundedProseChecker(
        Recording(_verdict(Decision.ESCALATE, conflict="canon has no date for this")),
        Authority.ADVISE,
    )

    verdict = _run(reader)

    assert verdict.decision == Decision.PASS and verdict.conflict == ""
    assert "canon has no date for this" in verdict.issues[-1].fix_hint
    assert verdict.issues[-1].severity == Severity.WARNING


def test_a_blocking_lens_keeps_its_teeth_on_the_unit_but_may_not_rule_on_canon():
    reader = BoundedProseChecker(
        Recording(_verdict(Decision.ESCALATE, conflict="canon contradicts itself")),
        Authority.BLOCK,
    )

    verdict = _run(reader)

    assert verdict.decision == Decision.REVISE, "an escalation is capped into a repairable issue"
    assert verdict.conflict == "", "nothing reaches the adjudicator"
    assert any("canon contradicts itself" in i.fix_hint for i in verdict.blocking_issues())


def test_full_authority_passes_the_verdict_through_untouched():
    original = _verdict(Decision.ESCALATE, conflict="canon contradicts itself")
    reader = BoundedProseChecker(Recording(original), Authority.ESCALATE)

    assert _run(reader) == original


# --------------------------------------------------------------------------------------------
# The shipped table
# --------------------------------------------------------------------------------------------

def test_the_default_gate_is_built_from_the_table_in_order():
    gate = build_prose_gate(FakeStructuredLLM(), samples=1)
    assert [r.name for r in gate] == ["canon_consistency", "micro_sense", "voice", "vitality", "intent"]


def test_only_the_measured_reader_is_sampled():
    """Sampling triples a reader's cost: C4 measured canon-consistency, and nothing else."""
    sampled = [spec for spec in PROSE_GATE if spec.sampled]
    assert len(sampled) == 1
    gate = build_prose_gate(FakeStructuredLLM(), samples=3)
    assert type(gate[0]).__name__ == "ConsensusProseChecker"
    assert [type(r).__name__ for r in gate[1:4]] == ["MicroSenseChecker", "AuthorVoiceChecker", "VitalityChecker"]


def test_checker_samples_1_turns_sampling_off_without_changing_the_readers():
    gate = build_prose_gate(FakeStructuredLLM(), samples=1)
    assert type(gate[0]).__name__ == "CanonConsistencyChecker"


def test_intent_reads_chapters_only_and_advises_until_it_is_calibrated():
    """
    The vitality lesson (C6), applied before the fact: an uncalibrated binary gate fires on
    everything and sends the whole book through the step that flattens it.
    """
    row = next(spec for spec in PROSE_GATE if spec.lens(FakeStructuredLLM(), None).name == "intent")
    assert row.scope is Scope.CHAPTER
    assert row.authority is Authority.ADVISE

    llm = FakeStructuredLLM()
    intent = build_prose_gate(llm, samples=1)[-1]
    verdict = _run(intent, scene=SCENE)

    assert verdict.decision == Decision.PASS
    assert llm.calls == [], "a scene never reaches the intent lens, so it costs nothing"


def test_every_row_says_why_it_is_configured_that_way():
    assert all(spec.note.strip() for spec in PROSE_GATE)
