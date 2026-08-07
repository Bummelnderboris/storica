"""
Tests for the v2 stages (P2: Conception + structured world/cast).

Run from the backend/ directory:
    venv/bin/python -m pytest app/v2/tests/ -q

No network: every stage is driven by `FakeStructuredLLM` with pre-built schema instances, so what
is under test is our contract (normalisation, the canon gate, the repair loop), not the model.
Tests are sync and drive the coroutines with `asyncio.run` to avoid an async-plugin dependency.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
import yaml

from app.v2.authors import load_author
from app.v2.brief import Brief, load_brief, save_brief
from app.v2.canon import CharacterRole, Premise, blocking, is_valid, load_canon, validate
from app.v2.llm import FakeStructuredLLM
from app.v2.pipeline import establish_canon
from app.v2.stages import conceive, develop_world_and_cast, draft_to_canon
from app.v2.stages.conception import ConceptionCandidates, ConceptionChoice, PremiseCandidate
from app.v2.stages.world_cast import (
    ArcDraft,
    CanonGateFailed,
    CharacterDraft,
    ConstraintsDraft,
    FactPair,
    RelationshipDraft,
    TimelineDraft,
    WorldCastDraft,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
AUTHORS_ROOT = REPO_ROOT / "authors"


# --------------------------------------------------------------------------------------------
# Fixtures / builders
# --------------------------------------------------------------------------------------------

@pytest.fixture
def brief() -> Brief:
    return Brief(
        author_id="duerrenmatt",
        spark="A death certificate the wrong man has to sign.",
        thoughts="Something about paperwork as absolution.",
        question_lines=["Can a bureaucracy absolve anyone?"],
        forbidden=["sentimental redemption"],
        language="de",
        chapter_count=5,
    )


@pytest.fixture
def author():
    return load_author("duerrenmatt", AUTHORS_ROOT)


def _candidate(n: int) -> PremiseCandidate:
    return PremiseCandidate(
        spark=f"spark {n}",
        central_question=f"question {n}?",
        thesis=f"thesis {n}",
        why_this_author=f"because {n}",
        question_line=f"line {n}",
        risk=f"risk {n}",
    )


def _arc() -> ArcDraft:
    return ArcDraft(want="w", need="n", flaw="f", trajectory="does not change")


def _character(cid: str, name: str, role: CharacterRole, aliases=None) -> CharacterDraft:
    return CharacterDraft(
        id=cid,
        canonical_name=name,
        aliases=aliases or [],
        role=role,
        facts=[FactPair(key="Profession", value="Amtsarzt")],
        arc=_arc(),
    )


def _draft(characters, relationships=None, timeline=None) -> WorldCastDraft:
    return WorldCastDraft(
        characters=characters,
        relationships=relationships or [],
        world_facts=[FactPair(key="setting", value="Lauenegg")],
        timeline=timeline or [],
        constraints=ConstraintsDraft(language="de", forbidden=["justice triumphs"], chapter_count=5),
    )


def _good_draft() -> WorldCastDraft:
    return _draft(
        characters=[
            _character("stettler", "Dr. Konrad Stettler", CharacterRole.PROTAGONIST, ["Stettler"]),
            _character("rutz", "Pfarrer Johannes Rutz", CharacterRole.SUPPORTING, ["Rutz", "der Pfarrer"]),
        ],
        relationships=[RelationshipDraft(a="stettler", b="rutz", type="debtor_of")],
        timeline=[TimelineDraft(id="t1", when="20y prior", event="the forgery", involves=["stettler"], order=1)],
    )


# --------------------------------------------------------------------------------------------
# Stage 1 — Conception
# --------------------------------------------------------------------------------------------

def test_conceive_generates_then_chooses(brief, author):
    chosen = _candidate(2)
    llm = FakeStructuredLLM(
        responses=[
            ConceptionCandidates(candidates=[_candidate(0), _candidate(1), chosen]),
            ConceptionChoice(chosen_index=2, reasoning="sharpest question", merged_from=[0], premise=chosen),
        ]
    )

    premise = asyncio.run(conceive(brief=brief, author=author, llm=llm, n_candidates=3))

    assert isinstance(premise, Premise)
    assert premise.central_question == "question 2?"
    assert premise.thesis == "thesis 2"
    # two calls: generate, then choose — and the author's obsessions drive both
    assert [c.schema for c in llm.calls] == ["ConceptionCandidates", "ConceptionChoice"]
    assert "Die Unmöglichkeit der Gerechtigkeit" in llm.calls[0].prompt
    assert "IMMUTABLE GROUND TRUTH" in llm.calls[0].prompt
    # the choice call must see the candidates it is choosing between
    assert "Candidate 2" in llm.calls[1].prompt


def test_conceive_rejects_empty_candidate_set(brief, author):
    llm = FakeStructuredLLM(responses=[ConceptionCandidates(candidates=[])])
    with pytest.raises(ValueError):
        asyncio.run(conceive(brief=brief, author=author, llm=llm))


# --------------------------------------------------------------------------------------------
# Draft → canon normalisation
# --------------------------------------------------------------------------------------------

def test_draft_to_canon_normalises_ids_and_facts(brief):
    draft = _draft(characters=[_character("Dr. Stettler", "Dr. Konrad Stettler", CharacterRole.PROTAGONIST)])
    canon = draft_to_canon(draft, premise=Premise(), author_id="duerrenmatt", brief=brief)

    assert list(canon.characters) == ["dr_stettler"]          # slugified, never a display name
    assert canon.characters["dr_stettler"].facts == {"profession": "Amtsarzt"}  # pairs → dict, key slugified
    assert canon.world_facts == {"setting": "Lauenegg"}
    assert canon.author_id == "duerrenmatt"


def test_draft_to_canon_resolves_name_references_to_ids(brief):
    """The classic slip: the model writes a relationship against a NAME. Resolve it, don't fail it."""
    draft = _draft(
        characters=[
            _character("stettler", "Dr. Konrad Stettler", CharacterRole.PROTAGONIST, ["Stettler"]),
            _character("rutz", "Pfarrer Johannes Rutz", CharacterRole.SUPPORTING, ["Rutz"]),
        ],
        relationships=[RelationshipDraft(a="Dr. Konrad Stettler", b="Rutz", type="debtor_of")],
        timeline=[TimelineDraft(id="t1", when="20y prior", event="x", involves=["Stettler"], order=1)],
    )
    canon = draft_to_canon(draft, premise=Premise(), author_id="duerrenmatt", brief=brief)

    assert (canon.relationships[0].a, canon.relationships[0].b) == ("stettler", "rutz")
    assert canon.timeline[0].involves == ["stettler"]
    assert is_valid(canon)


def test_draft_to_canon_merges_brief_constraints(brief):
    canon = draft_to_canon(_good_draft(), premise=Premise(), author_id="duerrenmatt", brief=brief)
    assert canon.constraints.language == "de"
    assert canon.constraints.chapter_count == 5
    # the brief's forbidden list is ground truth and survives alongside the author's
    assert canon.constraints.forbidden == ["sentimental redemption", "justice triumphs"]


def test_draft_to_canon_keeps_unresolvable_reference_for_the_validator(brief):
    """A reference we cannot resolve must stay dangling so the gate reports it."""
    draft = _draft(
        characters=[_character("stettler", "Dr. Konrad Stettler", CharacterRole.PROTAGONIST)],
        relationships=[RelationshipDraft(a="stettler", b="a_ghost", type="knows")],
    )
    canon = draft_to_canon(draft, premise=Premise(), author_id="duerrenmatt", brief=brief)
    assert {i.code for i in blocking(validate(canon))} == {"ref.relationship"}


# --------------------------------------------------------------------------------------------
# Stage 2 — the canon gate + repair loop
# --------------------------------------------------------------------------------------------

def test_world_cast_passes_gate_on_a_clean_draft(brief, author):
    llm = FakeStructuredLLM(responses=[_good_draft()])
    result = asyncio.run(
        develop_world_and_cast(premise=Premise(spark="s"), brief=brief, author=author, llm=llm)
    )

    assert result.is_valid and result.repairs == 0
    assert result.model.resolve_name("der Pfarrer") == "rutz"
    assert result.model.characters["stettler"].role == CharacterRole.PROTAGONIST


def test_name_collision_triggers_a_grounded_repair(brief, author):
    """The v1 Rutz failure: one name owned by two characters. The gate must catch and repair it."""
    fragmented = _draft(
        characters=[
            _character("stettler", "Dr. Konrad Stettler", CharacterRole.PROTAGONIST, ["Stettler"]),
            _character("rutz", "Pfarrer Johannes Rutz", CharacterRole.SUPPORTING, ["Rutz"]),
            _character("rutz_creditor", "Rutz", CharacterRole.BACKGROUND),  # same name, second id
        ]
    )
    llm = FakeStructuredLLM(responses=[fragmented, _good_draft()])

    result = asyncio.run(
        develop_world_and_cast(premise=Premise(spark="s"), brief=brief, author=author, llm=llm)
    )

    assert result.repairs == 1 and result.is_valid
    assert set(result.model.characters) == {"stettler", "rutz"}
    # the repair agent is handed the exact issues and the draft — never asked to re-invent the story
    repair_prompt = llm.calls[1].prompt
    assert "canon.name_collision" in repair_prompt
    assert "Do NOT invent a new character" in repair_prompt


def test_gate_raises_when_the_repair_budget_is_spent(brief, author):
    broken = _draft(
        characters=[_character("hero", "Hero", CharacterRole.PROTAGONIST)],
        relationships=[RelationshipDraft(a="hero", b="ghost", type="knows")],
    )
    llm = FakeStructuredLLM(responses=[broken, broken, broken])

    with pytest.raises(CanonGateFailed) as exc:
        asyncio.run(
            develop_world_and_cast(
                premise=Premise(), brief=brief, author=author, llm=llm, max_repairs=2
            )
        )

    assert any(i.code == "ref.relationship" for i in exc.value.issues)
    assert len(llm.calls) == 3  # draft + 2 repairs, then stop — bounded, no oscillation


def test_gate_can_return_invalid_canon_when_not_strict(brief, author):
    broken = _draft(
        characters=[_character("hero", "Hero", CharacterRole.PROTAGONIST)],
        relationships=[RelationshipDraft(a="hero", b="ghost", type="knows")],
    )
    llm = FakeStructuredLLM(responses=[broken])
    result = asyncio.run(
        develop_world_and_cast(
            premise=Premise(), brief=brief, author=author, llm=llm, max_repairs=0, strict=False
        )
    )
    assert not result.is_valid


def test_warnings_do_not_block(brief, author):
    """No protagonist is a warning, not a failure — the gate must not repair-loop on it."""
    llm = FakeStructuredLLM(
        responses=[_draft(characters=[_character("a", "A", CharacterRole.SUPPORTING)])]
    )
    result = asyncio.run(
        develop_world_and_cast(premise=Premise(), brief=brief, author=author, llm=llm)
    )
    assert result.is_valid and result.repairs == 0
    assert "cast.no_protagonist" in {i.code for i in result.issues}


# --------------------------------------------------------------------------------------------
# Brief: immutable ground truth
# --------------------------------------------------------------------------------------------

def test_brief_roundtrip_and_immutability(tmp_path, brief):
    save_brief(brief, tmp_path)
    assert load_brief(tmp_path) == brief
    with pytest.raises(FileExistsError):      # ground truth is written once, never edited
        save_brief(brief, tmp_path)
    with pytest.raises(Exception):            # and is frozen in memory too
        brief.spark = "something else"


# --------------------------------------------------------------------------------------------
# P2 end-to-end
# --------------------------------------------------------------------------------------------

def test_establish_canon_writes_validated_canon_and_trace(tmp_path, brief):
    novel = tmp_path / "test-novel"
    save_brief(brief, novel / "00_input")

    chosen = _candidate(1)
    llm = FakeStructuredLLM(
        responses=[
            ConceptionCandidates(candidates=[_candidate(0), chosen]),
            ConceptionChoice(chosen_index=1, reasoning="fits the brief", merged_from=[], premise=chosen),
            _good_draft(),
        ]
    )

    canon = asyncio.run(establish_canon(novel_dir=novel, authors_root=AUTHORS_ROOT, llm=llm))

    # canon is on disk, valid, and the premise survived from stage 1 into it
    on_disk = load_canon(novel / "01_canon")
    assert on_disk == canon
    assert is_valid(on_disk)
    assert on_disk.premise.central_question == "question 1?"
    assert on_disk.author_id == "duerrenmatt"
    assert (novel / "01_canon" / "history" / "v0001.json").exists()

    # every agent call is traced, prompt and artifact both
    traces = sorted((novel / "04_trace").glob("*.json"))
    assert [t.name for t in traces] == [
        "001_conception_candidates.json",
        "002_conception_choice.json",
        "003_world_cast.json",
    ]
    recorded = json.loads(traces[0].read_text())
    assert recorded["prompt"] and recorded["artifact"]["candidates"]


def test_author_model_loads_the_real_profile():
    author = load_author("duerrenmatt", AUTHORS_ROOT)
    assert author.name == "Friedrich Dürrenmatt"
    assert author.language == "de"
    assert "Zufall" in author.central_obsession
    assert "question-lines" in author.conception_block()
    assert "Steer AWAY" in author.voice_block()


def test_author_model_missing_profile_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_author("nobody", tmp_path)


def test_hemingway_author_also_loads():
    """P0 shipped two authors; the loader must not be duerrenmatt-shaped."""
    author = load_author("hemingway", AUTHORS_ROOT)
    assert author.id == "hemingway"
    assert author.profile.get("metadata", {}).get("name")
    assert yaml.safe_load  # sanity: the profile really is yaml-parsed above
