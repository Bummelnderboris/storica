"""
Tests for the prose checkers (P4/P5: micro-sense, author-voice, canon-consistency).

Run from the backend/ directory:
    venv/bin/python -m pytest app/v2/tests/ -q

No network: every checker is driven by `FakeStructuredLLM` with a pre-built `Verdict`, so what is
under test is our contract — the grounding we hand the reader, the rubric we hold it to, and the
verdict we pass back untouched — not the model's judgement. Tests are sync and drive the coroutines
with `asyncio.run` to avoid an async-plugin dependency.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from app.v2.authors import AuthorModel
from app.v2.canon import (
    Character,
    CharacterArc,
    CharacterRole,
    Constraints,
    Motif,
    Premise,
    Promise,
    Relationship,
    Severity,
    StoryModel,
    TimelineEvent,
)
from app.v2.checkers.base import CheckerIssue, Decision, Verdict
from app.v2.checkers.canon_consistency import CanonConsistencyChecker
from app.v2.checkers.micro_sense import MicroSenseChecker
from app.v2.checkers.prose_base import ProseChecker
from app.v2.checkers.voice import AuthorVoiceChecker
from app.v2.llm import FakeStructuredLLM
from app.v2.plan import ChapterSpec, SceneSpec, StateFact
from app.v2.trace import Tracer

CHECKERS = [MicroSenseChecker, AuthorVoiceChecker, CanonConsistencyChecker]


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
                aliases=["Stettler", "der Amtsarzt"],
                role=CharacterRole.PROTAGONIST,
                facts={"profession": "Amtsarzt", "secret": "forged Klara Vogel's death certificate"},
                arc=CharacterArc(want="ruhe", need="wahrheit", flaw="feigheit", trajectory="hardens"),
            ),
            "rutz": Character(
                canonical_name="Pfarrer Johannes Rutz",
                aliases=["Rutz", "der Pfarrer"],
                role=CharacterRole.SUPPORTING,
                facts={"office": "village priest", "relation": "old friend of Stettler"},
            ),
            "berta": Character(
                canonical_name="Berta Feuz",
                aliases=["die Feuz"],
                role=CharacterRole.SUPPORTING,
                facts={"status": "widow of Melchior Feuz"},
            ),
        },
        relationships=[Relationship(a="rutz", b="stettler", type="confessor_of")],
        world_facts={"setting": "Lauenegg, Graubünden", "location:chrachen": "gorge south of village"},
        timeline=[TimelineEvent(id="t1", when="20y prior", event="Klara Vogel dies", involves=["stettler"])],
        motifs=[Motif(id="formula_echo", desc="the phrase recurs identically", setup_ch=1, payoff_ch=3)],
        promises=[Promise(id="berta_question", desc="Berta's unanswered question", made_ch=1)],
        constraints=Constraints(language="de", forbidden=["sentimentale Erlösung"], chapter_count=5),
    )


@pytest.fixture
def spec() -> ChapterSpec:
    return ChapterSpec(
        chapter=1,
        title="Das Protokoll",
        purpose="Stettler signs the certificate and Berta sees him hesitate.",
        pov_character_id="stettler",
        present_character_ids=["stettler", "rutz", "berta"],
        advances_beats=["b1"],
        setups=["formula_echo"],
        payoffs=[],
        promises_made=["berta_question"],
        promises_kept=[],
        entry_state=[StateFact(key="body:location", value="im Chrachen")],
        exit_state=[StateFact(key="stettler:knows", value="dass Berta gefragt hat")],
        scenes=[
            SceneSpec(
                id="s1",
                location="Pfarrhaus",
                character_ids=["stettler", "rutz"],
                intent="Rutz asks Stettler what he wrote on the certificate.",
                turn="Stettler lies to the one man he has never lied to.",
            ),
            SceneSpec(
                id="s2",
                location="Küche Feuz",
                character_ids=["stettler", "berta"],
                intent="Berta asks her question.",
                turn="Stettler does not answer, and both know it.",
            ),
        ],
    )


@pytest.fixture
def author() -> AuthorModel:
    return AuthorModel(
        id="duerrenmatt",
        name="Friedrich Dürrenmatt",
        language="de",
        profile={},
        question_lines="- Kann Gerechtigkeit Zufall sein?",
        nudges=(
            "## Steer TOWARD\n"
            "- Nuechterne, sachliche Sprache bei grotesken Inhalten.\n\n"
            "## Steer AWAY (hard no)\n"
            "- Erklaerende Psychologie / Motivanalyse.\n"
            "- Triumphierende Aufloesung der Konflikte.\n"
        ),
        impression="A precise machine slowly going out of control.",
    )


PROSE = """Stettler legte das Formular auf den Tisch.

Der Pfarrer sah ihn an und sagte nichts. Draussen begann es zu schneien.

"Wie bei der Vogel?", fragte Berta."""


def _verdict(decision: Decision = Decision.REVISE, conflict: str = "") -> Verdict:
    return Verdict(
        decision=decision,
        summary="one sentence about the unit",
        issues=[
            CheckerIssue(
                unit='P2: "Draussen begann es zu schneien"',
                kind="micro-sense",
                severity=Severity.WARNING,
                canon_ref="setting",
                fix_hint="cut the sentence",
            )
        ],
        conflict=conflict,
    )


def _run(checker, *, canon, spec, author, scene=None, prose=PROSE) -> Verdict:
    return asyncio.run(
        checker.check_prose(prose=prose, canon=canon, spec=spec, author=author, scene=scene)
    )


# --------------------------------------------------------------------------------------------
# Shared contract: verdict pass-through, trace, grounding, slicing, protocol
# --------------------------------------------------------------------------------------------

@pytest.mark.parametrize("cls", CHECKERS)
def test_checker_returns_the_verdict_it_is_given(cls, canon, spec, author):
    given = _verdict()
    llm = FakeStructuredLLM(responses=[given])
    verdict = _run(cls(llm), canon=canon, spec=spec, author=author)

    assert verdict is given
    assert llm.calls[0].schema == "Verdict"
    assert llm.calls[0].model == "sonnet"


@pytest.mark.parametrize("cls", CHECKERS)
def test_checker_records_the_call_in_the_trace(cls, tmp_path, canon, spec, author):
    """Every judgement lands on disk: a run nobody watched still has to be reconstructable (§6.5)."""
    llm = FakeStructuredLLM(responses=[_verdict()])
    checker = cls(llm, tracer=Tracer(tmp_path))
    _run(checker, canon=canon, spec=spec, author=author, scene=spec.scenes[0])

    written = list(tmp_path.glob("*.json"))
    assert len(written) == 1
    assert written[0].name.endswith(f"{checker.name}_check_ch01_s1.json")

    payload = json.loads(written[0].read_text(encoding="utf-8"))
    assert payload["note"] == Decision.REVISE.value
    assert payload["system"] == llm.calls[0].system
    assert payload["artifact"]["summary"] == "one sentence about the unit"


@pytest.mark.parametrize("cls", CHECKERS)
def test_prompt_is_grounded_in_the_canon_slice_and_the_assignment(cls, canon, spec, author):
    llm = FakeStructuredLLM(responses=[_verdict()])
    _run(cls(llm), canon=canon, spec=spec, author=author, scene=spec.scenes[0])
    prompt = llm.calls[0].prompt

    assert "# Canon slice (SOURCE OF TRUTH" in prompt
    assert "Dr. Konrad Stettler" in prompt
    assert "der Amtsarzt" in prompt                      # aliases travel with the character
    assert "profession: Amtsarzt" in prompt              # and so do the facts
    assert "Lauenegg" in prompt
    assert spec.purpose in prompt
    assert spec.scenes[0].intent in prompt
    assert spec.scenes[0].turn in prompt
    assert PROSE.splitlines()[0] in prompt


@pytest.mark.parametrize("cls", CHECKERS)
def test_prompt_says_the_checker_did_not_write_the_prose(cls, canon, spec, author):
    """Fresh context is the mechanism (principle 4) — the reader is told it has none."""
    llm = FakeStructuredLLM(responses=[_verdict()])
    _run(cls(llm), canon=canon, spec=spec, author=author)
    system = llm.calls[0].system

    assert "did not write" in system
    assert "no memory of how it was produced" in system


@pytest.mark.parametrize("cls", CHECKERS)
def test_no_checker_asks_for_a_score(cls, canon, spec, author):
    """v1's weighted average (F8) is the thing these checkers replace — never re-introduce it."""
    llm = FakeStructuredLLM(responses=[_verdict()])
    _run(cls(llm), canon=canon, spec=spec, author=author)

    assert "do NOT score" in llm.calls[0].system
    assert "score" in llm.calls[0].system  # stated as a rule, not merely omitted


@pytest.mark.parametrize("cls", CHECKERS)
def test_scene_scoped_check_slices_down_to_that_scenes_cast(cls, canon, spec, author):
    llm = FakeStructuredLLM(responses=[_verdict()])
    _run(cls(llm), canon=canon, spec=spec, author=author, scene=spec.scenes[0])
    prompt = llm.calls[0].prompt

    assert "### stettler" in prompt
    assert "### rutz" in prompt
    assert "### berta" not in prompt


@pytest.mark.parametrize("cls", CHECKERS)
def test_chapter_scoped_check_covers_the_whole_chapter_cast(cls, canon, spec, author):
    llm = FakeStructuredLLM(responses=[_verdict()])
    _run(cls(llm), canon=canon, spec=spec, author=author)
    prompt = llm.calls[0].prompt

    for cid in spec.present_character_ids:
        assert f"### {cid}" in prompt
    assert "formula_echo" in prompt        # the ledger entries assigned to this chapter
    assert "berta_question" in prompt


@pytest.mark.parametrize("cls", CHECKERS)
def test_checker_satisfies_the_prose_checker_protocol(cls, canon):
    assert isinstance(cls(FakeStructuredLLM()), ProseChecker)


@pytest.mark.parametrize("cls", CHECKERS)
def test_unit_label_distinguishes_scene_from_chapter(cls, tmp_path, canon, spec, author):
    llm = FakeStructuredLLM(responses=[_verdict(), _verdict()])
    checker = cls(llm, tracer=Tracer(tmp_path))
    _run(checker, canon=canon, spec=spec, author=author)
    _run(checker, canon=canon, spec=spec, author=author, scene=spec.scenes[1])

    names = sorted(p.name for p in tmp_path.glob("*.json"))
    assert names[0].endswith(f"{checker.name}_check_ch01.json")
    assert names[1].endswith(f"{checker.name}_check_ch01_s2.json")


# --------------------------------------------------------------------------------------------
# Micro-sense: paragraph-level judgement, quoted spans
# --------------------------------------------------------------------------------------------

def test_micro_sense_numbers_the_paragraphs_for_localised_findings(canon, spec, author):
    llm = FakeStructuredLLM(responses=[_verdict()])
    _run(MicroSenseChecker(llm), canon=canon, spec=spec, author=author)
    prompt = llm.calls[0].prompt

    assert "[P1] Stettler legte das Formular" in prompt
    assert "[P2] Der Pfarrer sah ihn an" in prompt
    assert '[P3] "Wie bei der Vogel?"' in prompt


def test_micro_sense_asks_for_paragraph_judgement_and_quoted_spans(canon, spec, author):
    """An issue that cannot be localised forces a rewrite, and rewrites are how F12 happened."""
    llm = FakeStructuredLLM(responses=[_verdict()])
    _run(MicroSenseChecker(llm), canon=canon, spec=spec, author=author)
    prompt, system = llm.calls[0].prompt, llm.calls[0].system

    assert "one numbered paragraph at a time" in prompt
    assert "quoted span of at most twelve words" in prompt
    assert "always quote" in prompt
    assert "pinned to a paragraph and a quoted span" in system


def test_micro_sense_targets_hallucination_filler_and_broken_situations(canon, spec, author):
    llm = FakeStructuredLLM(responses=[_verdict()])
    _run(MicroSenseChecker(llm), canon=canon, spec=spec, author=author)
    prompt = llm.calls[0].prompt

    assert "hallucination" in prompt
    assert "physical logic" in prompt and "social logic" in prompt
    assert "could be deleted with nothing lost" in prompt
    assert "Abstraction\n   standing in for the concrete event" in prompt
    assert "does not proceed" in prompt          # sentences that do not follow from each other


def test_micro_sense_stays_out_of_voice_and_plot(canon, spec, author):
    """Three rubrics, three failure classes: overlap would make the repair loop chase ghosts."""
    system = llm_system(MicroSenseChecker, canon, spec, author)
    assert "not the voice checker and not the continuity checker" in system


# --------------------------------------------------------------------------------------------
# Author-voice: forbidden list, steer-away list, language
# --------------------------------------------------------------------------------------------

def test_voice_prompt_carries_the_authors_steering_material(canon, spec, author):
    llm = FakeStructuredLLM(responses=[_verdict()])
    _run(AuthorVoiceChecker(llm), canon=canon, spec=spec, author=author)
    prompt = llm.calls[0].prompt

    assert "Steer AWAY (hard no)" in prompt
    assert "Erklaerende Psychologie / Motivanalyse." in prompt
    assert "Steer TOWARD" in prompt
    assert author.impression in prompt


def test_voice_prompt_carries_the_forbidden_list_and_target_language(canon, spec, author):
    llm = FakeStructuredLLM(responses=[_verdict()])
    _run(AuthorVoiceChecker(llm), canon=canon, spec=spec, author=author)
    prompt = llm.calls[0].prompt

    assert "GROUND TRUTH" in prompt
    assert "sentimentale Erlösung" in prompt
    assert "de — the prose must be in this language" in prompt


def test_voice_treats_the_forbidden_list_as_blocking_and_refuses_to_be_a_prose_critic(canon, spec, author):
    llm = FakeStructuredLLM(responses=[_verdict()])
    _run(AuthorVoiceChecker(llm), canon=canon, spec=spec, author=author)
    prompt, system = llm.calls[0].prompt, llm.calls[0].system

    assert "is a\n   BLOCKING issue, no matter how well it is written" in prompt
    assert "not yours to weigh against anything" in prompt
    assert "NOT a general prose critic" in system
    assert "If your issue would read the same for any novel by any author, do not raise it." in system


# --------------------------------------------------------------------------------------------
# Canon-consistency: no canon edits, no bridging facts, escalation instead
# --------------------------------------------------------------------------------------------

def test_canon_consistency_forbids_canon_edits_and_bridging_facts(canon, spec, author):
    """F11/F12: a contradiction that gets 'reconciled' becomes elaborated false canon."""
    system = llm_system(CanonConsistencyChecker, canon, spec, author)

    assert "Never propose a change to canon." in system
    assert "Never invent a bridging fact." in system
    assert "priest AND a private creditor" in system
    assert "If canon looks wrong, escalate and describe the conflict" in system


def test_canon_consistency_returns_an_escalating_verdict_intact(canon, spec, author):
    """The checker reports; the caller decides. Raising here would take that choice away."""
    escalated = _verdict(
        decision=Decision.ESCALATE,
        conflict="canon calls Rutz a priest and the timeline has him ordained after the funeral",
    )
    llm = FakeStructuredLLM(responses=[escalated])
    verdict = _run(CanonConsistencyChecker(llm), canon=canon, spec=spec, author=author)

    assert verdict.decision is Decision.ESCALATE
    assert verdict.conflict == escalated.conflict


def test_canon_consistency_prompt_carries_the_complete_name_registry(canon, spec, author):
    """A name attached to the wrong person is only visible against the full roster (F7/F9)."""
    llm = FakeStructuredLLM(responses=[_verdict()])
    _run(CanonConsistencyChecker(llm), canon=canon, spec=spec, author=author, scene=spec.scenes[0])
    prompt = llm.calls[0].prompt

    assert "# Name registry (COMPLETE" in prompt
    assert "- berta = Berta Feuz" in prompt      # present even though berta is not in this scene
    assert "- rutz = Pfarrer Johannes Rutz" in prompt


def test_canon_consistency_targets_role_drift_and_entry_exit_state(canon, spec, author):
    llm = FakeStructuredLLM(responses=[_verdict()])
    _run(CanonConsistencyChecker(llm), canon=canon, spec=spec, author=author)
    prompt = llm.calls[0].prompt

    assert "village priest\n   who acts as a creditor" in prompt
    assert "Facts that changed meaning" in prompt
    assert "Timeline" in prompt
    assert "body:location: im Chrachen" in prompt
    assert "stettler:knows: dass Berta gefragt hat" in prompt


def test_canon_consistency_treats_every_contradiction_as_blocking(canon, spec, author):
    llm = FakeStructuredLLM(responses=[_verdict()])
    _run(CanonConsistencyChecker(llm), canon=canon, spec=spec, author=author)

    assert "BLOCKING: every contradiction with canon, without exception." in llm.calls[0].prompt


# --------------------------------------------------------------------------------------------
# Helper
# --------------------------------------------------------------------------------------------

def llm_system(cls, canon, spec, author) -> str:
    llm = FakeStructuredLLM(responses=[_verdict()])
    _run(cls(llm), canon=canon, spec=spec, author=author)
    return llm.calls[0].system
