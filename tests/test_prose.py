"""
Tests for P4 stage 5: grounded, scene-by-scene prose and the `03_drafts/` store.

Run from the repo root:
    .venv/bin/python -m pytest tests/ -q

Offline: every LLM call is served by `FakeStructuredLLM` and every checker by `FakeProseChecker`,
so what is under test is the *contract* of the prose stage — is each scene grounded in the canon of
who is actually in it (F5/F9), does a blocking issue drive exactly one bounded repair, does a
warning stay a warning (F8), does an escalation stop the run instead of being smoothed over, and
does a stub cost nothing to reject.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List, Optional

import pytest

from storica.authors import load_author
from storica.canon import (
    Character,
    CharacterArc,
    CharacterRole,
    Constraints,
    Premise,
    Relationship,
    Severity,
    StoryModel,
    TimelineEvent,
)
from storica.checkers import Decision, Escalation, Verdict
from storica.checkers.base import CheckerIssue
from storica.checkers.prose_base import ProseChecker
from storica.drafts import (
    chapter_draft_path,
    drafted_chapters,
    load_chapter_draft,
    load_chapter_draft_if_present,
    save_chapter_draft,
)
from storica.llm import FakeStructuredLLM
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
)
from storica.stages import promote_ledger, to_macro_arc
from storica.stages.prose import SCENE_DIVIDER, ProseGateFailed, write_chapter

REPO_ROOT = Path(__file__).resolve().parents[1]
AUTHORS_ROOT = REPO_ROOT / "authors"

# The tests use short prose, so the stub floor is lowered for everything except the tests that are
# explicitly about the floor itself.
SHORT_OK = 40


# --------------------------------------------------------------------------------------------
# Builders
# --------------------------------------------------------------------------------------------

def _canon() -> StoryModel:
    return StoryModel(
        premise=Premise(spark="a body in the gorge", central_question="can he resist?",
                        thesis="guilt administered", why_this_author="chance vs plan"),
        author_id="duerrenmatt",
        characters={
            "stettler": Character(
                canonical_name="Dr. Konrad Stettler",
                aliases=["Stettler", "der Amtsarzt"],
                role=CharacterRole.PROTAGONIST,
                facts={"profession": "Amtsarzt"},
                arc=CharacterArc(want="close the case", need="confess", flaw="order",
                                 trajectory="hardens"),
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
        timeline=[TimelineEvent(id="t1", when="20y prior", event="the forgery",
                                involves=["stettler"], order=1)],
        constraints=Constraints(language="de", forbidden=["justice triumphs"], chapter_count=3),
    )


def _arc_draft() -> MacroArcDraft:
    return MacroArcDraft(
        chapter_count=3,
        shape="A man who files his guilt is handed the chance to close the file for good.",
        acts=[
            Act(number=1, title="The body", chapters=[1, 2], purpose="the chance is offered"),
            Act(number=2, title="The signature", chapters=[3], purpose="he takes it"),
        ],
        turning_points=[TurningPoint(id="tp1", chapter=3, description="he signs",
                                     reverses="that he could still confess")],
        arc_beats=[
            ArcBeat(id="b1", character_id="stettler", chapter=1,
                    beat="is handed the certificate", advances="want"),
            ArcBeat(id="b2", character_id="rutz", chapter=3, beat="stops asking",
                    advances="trajectory"),
        ],
        motifs=[MotifDraft(id="formula_echo", desc="the same phrase recurs", setup_ch=1, payoff_ch=3)],
        promises=[PromiseDraft(id="berta_question", desc="the unanswered question", made_ch=1, kept_ch=3)],
        tension_curve=[
            TensionPoint(chapter=1, tension=3, note="the offer"),
            TensionPoint(chapter=2, tension=6, note="the doubt"),
            TensionPoint(chapter=3, tension=9, note="the signature"),
        ],
    )


def _planned():
    return promote_ledger(_canon(), _arc_draft()), to_macro_arc(_arc_draft())


S1 = SceneSpec(id="s1", location="setting", character_ids=["stettler"],
               intent="carries b1: the certificate reaches him",
               turn="he realises whose signature is required")
S2 = SceneSpec(id="s2", location="Pfarrhaus", character_ids=["stettler", "rutz"],
               intent="the question is asked out loud",
               turn="he lies to a friend for the first time")


def _spec(**over) -> ChapterSpec:
    base = dict(
        chapter=1,
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
        scenes=[S1, S2],
    )
    base.update(over)
    return ChapterSpec(**base)


def _prose(marker: str) -> str:
    return (f"{marker}. Der Amtsarzt legte das Formular auf den Tisch und las die Zeile noch "
            f"einmal, Wort für Wort, bis sie nichts mehr bedeutete.")


def _verdict(decision=Decision.PASS, issues=None, conflict="") -> Verdict:
    return Verdict(decision=decision, summary="judged", issues=issues or [], conflict=conflict)


def _issue(severity=Severity.BLOCKING, fix_hint="cut the sentence that names Rutz a creditor") -> CheckerIssue:
    return CheckerIssue(unit="s1", kind="coherence", severity=severity,
                        canon_ref="rutz", fix_hint=fix_hint)


class FakeProseChecker:
    """A `ProseChecker` double: serves queued verdicts and records what it was asked to judge."""

    def __init__(self, *verdicts: Verdict, name: str = "fake", default: Optional[Verdict] = None):
        self.name = name
        self.verdicts: List[Verdict] = list(verdicts)
        self.default = default if default is not None else _verdict()
        self.units: List[Optional[str]] = []
        self.prose: List[str] = []

    async def check_prose(self, *, prose, canon, spec, author, scene=None, draw=1) -> Verdict:
        self.units.append(scene.id if scene is not None else None)
        self.prose.append(prose)
        return self.verdicts.pop(0) if self.verdicts else self.default


@pytest.fixture(scope="module")
def author():
    return load_author("duerrenmatt", AUTHORS_ROOT)


def _write(llm, author, **over):
    canon, arc = _planned()
    kwargs = dict(spec=_spec(), canon=canon, arc=arc, author=author, llm=llm,
                  min_scene_chars=SHORT_OK)
    kwargs.update(over)
    return asyncio.run(write_chapter(**kwargs))


# --------------------------------------------------------------------------------------------
# The clean path
# --------------------------------------------------------------------------------------------

def test_a_clean_chapter_is_one_call_per_scene(author):
    llm = FakeStructuredLLM(texts=[_prose("Erste Szene"), _prose("Zweite Szene")])

    result = _write(llm, author)

    assert [c.schema for c in llm.calls] == ["<text>", "<text>"]
    assert result.repairs == 0 and result.is_valid
    assert len(result.scenes) == 2
    assert "Erste Szene" in result.text and "Zweite Szene" in result.text
    assert result.text.startswith("# Das Protokoll")
    assert SCENE_DIVIDER in result.text
    assert result.chapter == 1


def test_prose_is_written_with_generate_never_parse(author):
    """Prose must not be schema-constrained — `parse` is for decisions, `generate` for text."""
    llm = FakeStructuredLLM(texts=[_prose("a"), _prose("b")])
    _write(llm, author)
    assert all(c.schema == "<text>" for c in llm.calls)


# --------------------------------------------------------------------------------------------
# Grounding — the F5/F9 fix
# --------------------------------------------------------------------------------------------

def test_scene_prompt_carries_the_full_canon_of_whoever_is_in_that_scene(author):
    """A scene is grounded in complete canon for its cast — never a truncated blueprint (F5)."""
    llm = FakeStructuredLLM(texts=[_prose("a"), _prose("b")])
    _write(llm, author)
    prompt = llm.calls[0].prompt

    assert "Canon slice (SOURCE OF TRUTH" in prompt
    assert "Dr. Konrad Stettler" in prompt and "der Amtsarzt" in prompt   # aliases travel with the id
    assert "profession: Amtsarzt" in prompt
    assert "want: close the case" in prompt
    assert "justice triumphs" in prompt                                   # the forbidden list grounds too
    # scene 1 is Stettler alone: the priest's canon is not in this call
    assert "Pfarrer Johannes Rutz" not in prompt
    # ...and it is, in the scene he is actually in
    assert "Pfarrer Johannes Rutz" in llm.calls[1].prompt


def test_scene_prompt_names_the_macro_assignment_by_id(author):
    """Macro intent rides into the micro call explicitly (DESIGN §7) — named, not implied."""
    llm = FakeStructuredLLM(texts=[_prose("a"), _prose("b")])
    _write(llm, author)
    prompt = llm.calls[0].prompt

    assert "[b1] stettler: is handed the certificate" in prompt
    assert "plant motif [formula_echo]" in prompt
    assert "make promise [berta_question]" in prompt
    assert "carries b1: the certificate reaches him" in prompt            # the scene's intent
    assert "he realises whose signature is required" in prompt            # the scene's turn
    assert "Stettler is handed the one case he cannot file honestly." in prompt  # chapter purpose
    assert "Steer AWAY" in prompt                                          # the author's voice block


def test_scene_prompt_demands_the_novels_language(author):
    llm = FakeStructuredLLM(texts=[_prose("a"), _prose("b")])
    _write(llm, author)
    assert "German (Deutsch)" in llm.calls[0].prompt


def test_second_scene_prompt_carries_the_whole_chapter_so_far(author):
    """Not an 800-character tail: scene 2 must see everything scene 1 fixed, from its first line."""
    first_scene = "Der erste Satz der ersten Szene. " + _prose("Erste Szene")
    llm = FakeStructuredLLM(texts=[first_scene, _prose("Zweite Szene")])
    _write(llm, author)

    second = llm.calls[1].prompt
    assert "this chapter so far" in second
    assert "Der erste Satz der ersten Szene." in second
    assert "bis sie nichts mehr bedeutete." in second


def test_opening_scene_carries_the_previous_chapters_tail(author):
    llm = FakeStructuredLLM(texts=[_prose("a"), _prose("b")])
    _write(llm, author, previous_tail="Er unterschrieb nicht.")

    first = llm.calls[0].prompt
    assert "the end of the previous chapter" in first
    assert "Er unterschrieb nicht." in first


# --------------------------------------------------------------------------------------------
# Checkers and repair
# --------------------------------------------------------------------------------------------

def test_checkers_run_on_every_scene_and_once_on_the_whole_chapter(author):
    """The smallest meaningful unit first, so a bad scene is localised and not averaged away (F8)."""
    llm = FakeStructuredLLM(texts=[_prose("a"), _prose("b")])
    checker = FakeProseChecker()

    _write(llm, author, checkers=[checker])

    assert checker.units == ["s1", "s2", None]
    assert checker.prose[-1].startswith("# Das Protokoll")   # the chapter pass sees the assembly


def test_a_blocking_issue_drives_exactly_one_repair(author):
    llm = FakeStructuredLLM(texts=[_prose("Erste Fassung"), _prose("Reparierte Fassung")])
    checker = FakeProseChecker(_verdict(Decision.REVISE, issues=[_issue()]))

    result = _write(llm, author, spec=_spec(scenes=[S1]), checkers=[checker])

    assert result.repairs == 1 and result.is_valid
    assert "Reparierte Fassung" in result.text and "Erste Fassung" not in result.text


def test_the_repair_prompt_names_the_fix_and_forbids_inventing_a_bridging_fact(author):
    llm = FakeStructuredLLM(texts=[_prose("Erste Fassung"), _prose("Reparierte Fassung")])
    checker = FakeProseChecker(_verdict(Decision.REVISE, issues=[_issue()]))

    _write(llm, author, spec=_spec(scenes=[S1]), checkers=[checker])
    repair = llm.calls[1].prompt

    assert "cut the sentence that names Rutz a creditor" in repair       # the exact fix_hint
    assert "Erste Fassung" in repair                                      # the prose under repair
    assert "Canon slice (SOURCE OF TRUTH" in repair                       # grounded, so it can't drift
    assert "Change ONLY the spans the issues above name" in repair
    assert "byte-identical" in repair
    assert "canon wins" in repair
    assert "You may not invent a fact" in repair


def test_a_canon_contradiction_short_circuits_the_other_readers(author):
    """defaults.py's promise, kept: a contradiction makes texture and voice judgements moot."""
    llm = FakeStructuredLLM(texts=[_prose("Erste Fassung"), _prose("Reparierte Fassung")])
    canon_reader = FakeProseChecker(_verdict(Decision.REVISE, issues=[_issue()]), name="canon_consistency")
    voice = FakeProseChecker(name="voice")

    result = _write(llm, author, spec=_spec(scenes=[S1]), checkers=[canon_reader, voice])

    assert result.repairs == 1 and result.is_valid
    # voice was skipped on the contradicted draft, then ran on the repaired scene and the chapter
    assert voice.prose[0].startswith("Reparierte Fassung")
    assert voice.prose[1].startswith("# Das Protokoll")
    assert len(canon_reader.prose) == 3


def test_a_blocking_texture_issue_does_not_short_circuit(author):
    llm = FakeStructuredLLM(texts=[_prose("Erste Fassung"), _prose("Reparierte Fassung")])
    micro = FakeProseChecker(_verdict(Decision.REVISE, issues=[_issue()]), name="micro_sense")
    voice = FakeProseChecker(name="voice")

    _write(llm, author, spec=_spec(scenes=[S1]), checkers=[micro, voice])

    assert len(voice.prose) == 3   # repair sees the union of everything the readers found


def test_when_every_candidate_is_a_stub_the_last_one_goes_to_repair_without_another_draw(author):
    llm = FakeStructuredLLM(texts=["kurz 1", "kurz 2", "kurz 3", _prose("Reparierte Fassung")])
    checker = FakeProseChecker()

    result = _write(llm, author, spec=_spec(scenes=[S1]), checkers=[checker], n_candidates=3)

    assert result.is_valid and result.repairs == 1
    generates = [c for c in llm.calls if c.schema == "<text>"]
    assert len(generates) == 4                       # 3 draws + 1 repair, no 4th draw
    assert "kurz 3" in generates[3].prompt           # the last stub is what was repaired


def test_a_warning_verdict_does_not_spin_the_repair_loop(author):
    """Only blocking issues fire repair — v1's averaged gate is exactly what we are not doing."""
    llm = FakeStructuredLLM(texts=[_prose("a")])
    checker = FakeProseChecker(_verdict(Decision.REVISE, issues=[_issue(Severity.WARNING)]))

    result = _write(llm, author, spec=_spec(scenes=[S1]), checkers=[checker])

    assert result.repairs == 0 and result.is_valid
    assert any(i.code == "fake.coherence" for i in result.issues)


def test_an_escalating_checker_stops_the_run(author):
    llm = FakeStructuredLLM(texts=[_prose("a")])
    checker = FakeProseChecker(
        _verdict(Decision.ESCALATE, conflict="canon has Rutz in two places at once"))

    with pytest.raises(Escalation) as exc:
        _write(llm, author, spec=_spec(scenes=[S1]), checkers=[checker])

    assert exc.value.unit == "ch01_s1"
    assert "two places at once" in exc.value.conflict


def test_repair_budget_exhaustion_raises_when_strict(author):
    llm = FakeStructuredLLM(texts=[_prose(str(i)) for i in range(3)])
    checker = FakeProseChecker(default=_verdict(Decision.REVISE, issues=[_issue()]))

    with pytest.raises(ProseGateFailed) as exc:
        _write(llm, author, spec=_spec(scenes=[S1]), checkers=[checker], max_repairs=2)

    assert len(llm.calls) == 3                                    # one draft, two repairs, then stop
    assert any(i.code == "fake.coherence" for i in exc.value.issues)


def test_repair_budget_exhaustion_returns_an_invalid_result_when_lenient(author):
    """`strict=False` hands the unit back flagged, so a later phase can quarantine it (§6.5)."""
    llm = FakeStructuredLLM(texts=[_prose(str(i)) for i in range(5)])
    checker = FakeProseChecker(default=_verdict(Decision.REVISE, issues=[_issue()]))

    result = _write(llm, author, spec=_spec(scenes=[S1]), checkers=[checker],
                    max_repairs=2, strict=False)

    assert not result.is_valid
    assert result.repairs == 4                                    # two on the scene, two on the chapter
    assert result.text


# --------------------------------------------------------------------------------------------
# Cheap before expensive
# --------------------------------------------------------------------------------------------

def test_an_empty_scene_fails_deterministically_without_a_checker_call(author):
    llm = FakeStructuredLLM(texts=["", "", ""])
    checker = FakeProseChecker()

    with pytest.raises(ProseGateFailed) as exc:
        _write(llm, author, spec=_spec(scenes=[S1]), checkers=[checker], max_repairs=2)

    assert checker.units == []                                    # no LLM judgement spent on nothing
    assert any(i.code == "prose.empty" for i in exc.value.issues)
    assert "Write the full text this time" in llm.calls[1].prompt  # empty is regenerated, not edited


def test_a_stub_scene_is_rejected_by_length_alone(author):
    llm = FakeStructuredLLM(texts=["Er ging.", "Er ging.", "Er ging."])
    checker = FakeProseChecker()

    with pytest.raises(ProseGateFailed) as exc:
        _write(llm, author, spec=_spec(scenes=[S1]), checkers=[checker],
               max_repairs=2, min_scene_chars=400)

    assert checker.units == []
    assert any(i.code == "prose.stub" for i in exc.value.issues)


def test_the_fake_checker_satisfies_the_prose_checker_protocol():
    assert isinstance(FakeProseChecker(), ProseChecker)


# --------------------------------------------------------------------------------------------
# The draft store
# --------------------------------------------------------------------------------------------

def test_draft_store_roundtrips(tmp_path):
    text = "# Das Protokoll\n\nDer Amtsarzt las die Zeile noch einmal.\n"
    path = save_chapter_draft(text, tmp_path, 1)

    assert path == chapter_draft_path(tmp_path, 1) == tmp_path / "ch01.md"
    assert load_chapter_draft(tmp_path, 1) == text
    assert load_chapter_draft_if_present(tmp_path, 1) == text
    assert load_chapter_draft_if_present(tmp_path, 2) is None


def test_drafted_chapters_lists_what_is_on_disk(tmp_path):
    assert drafted_chapters(tmp_path / "not_yet") == []

    save_chapter_draft("a", tmp_path, 3)
    save_chapter_draft("b", tmp_path, 1)
    (tmp_path / "notes.md").write_text("not a chapter", encoding="utf-8")

    assert drafted_chapters(tmp_path) == [1, 3]


def test_each_repair_pass_is_its_own_draw(author):
    """Under replay, a repair whose prompt repeats byte-for-byte must be a new call, not a cache hit."""
    llm = FakeStructuredLLM(texts=[_prose("Erste"), _prose("Erste"), _prose("Dritte")])
    checker = FakeProseChecker(_verdict(Decision.REVISE, issues=[_issue()]),
                               _verdict(Decision.REVISE, issues=[_issue()]))

    result = _write(llm, author, spec=_spec(scenes=[S1]), checkers=[checker], max_repairs=2)

    assert result.repairs == 2 and result.is_valid
    generates = [c for c in llm.calls if c.schema == "<text>"]
    assert [c.draw for c in generates] == [1, 1, 2]     # scene, repair 1, repair 2


def test_the_shipped_gate_reads_each_scene_four_times_and_the_chapter_twice(author):
    """
    The trigger, end to end. Four readers judge every scene. On the assembled chapter only the two
    chapter-scale questions are asked: a contradiction between scenes (canon-consistency) and
    whether the assignment was delivered (intent). Re-asking the local readers there was a second
    fresh draw on text they had already passed (C7).
    """
    from storica.checkers import default_prose_checkers
    from storica.checkers.base import Verdict

    llm = FakeStructuredLLM(
        texts=[_prose("Erste"), _prose("Zweite")],
        responses=[_verdict(Decision.PASS) for _ in range(20)],
    )

    result = _write(llm, author, checkers=default_prose_checkers(llm, samples=1))

    judgements = [c for c in llm.calls if c.schema == Verdict.__name__]
    intent_calls = [c for c in judgements if "You are not the other readers." in c.prompt]
    assert result.is_valid
    assert len(judgements) == 10, "4 readers x 2 scenes, then canon + intent on the assembled chapter"
    assert len(intent_calls) == 1
    assert "# The prose as written" in intent_calls[0].prompt


# --------------------------------------------------------------------------------------------
# What the writer knows about the craft (not only what it must avoid)
# --------------------------------------------------------------------------------------------

def test_the_writer_sees_the_author_s_craft_not_only_the_no_list(author):
    """The judges were shown the impression; the maker had ~200 words of nudges. Now it has both."""
    llm = FakeStructuredLLM(texts=[_prose("a"), _prose("b")])
    _write(llm, author)
    prompt = llm.calls[0].prompt

    assert "Steer AWAY" in prompt                                     # the nudges are still there
    assert "## Dialogue" in prompt and "Dialoge sind Duelle" in prompt  # profile: dialogue style
    assert "## Register samples" in prompt and "Never copy a sentence" in prompt
    assert "What it feels like to read Friedrich Dürrenmatt" in prompt


def test_the_writer_pictures_the_scene_before_drafting_it(author):
    llm = FakeStructuredLLM(texts=[_prose("a"), _prose("b")])
    _write(llm, author)
    prompt = llm.calls[0].prompt
    assert "Before you write — privately, and never on the page" in prompt
    assert "what will they not say" in prompt


def test_the_writer_is_told_what_it_may_invent(author):
    from storica.canon import INVENTION_POLICY
    from storica.stages.prose import SYSTEM as WRITER_SYSTEM

    assert INVENTION_POLICY in WRITER_SYSTEM
    assert "a date, an hour, a distance" in WRITER_SYSTEM
    assert "never invent a fact about a person, a place, a time" not in WRITER_SYSTEM


@pytest.mark.parametrize("author_id", ["duerrenmatt", "hemingway"])
def test_every_shipped_author_renders_a_writer_block(author_id):
    block = load_author(author_id, AUTHORS_ROOT).writer_block()
    assert block.startswith("# Writing as ")
    assert "## Sentences" in block and "(none recorded)" not in block.split("## Register samples")[0]
