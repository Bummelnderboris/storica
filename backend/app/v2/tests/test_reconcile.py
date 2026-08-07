"""
Tests for stage 6 — Reconcile (`app/v2/stages/reconcile.py`).

Run from the backend/ directory:
    venv/bin/python -m pytest app/v2/tests/ -q

Offline: the extraction call is served by `FakeStructuredLLM`, so what is under test is our
contract — classify new / consistent / contradiction, never overwrite canon, never fragment a
name, and only advance the ledger for work the prose actually did.

The load-bearing test in this file is
`test_a_fact_that_contradicts_canon_is_flagged_and_canon_is_unchanged`: v1 died at exactly that
point (F9 → F10 → F11 → F12).
"""

from __future__ import annotations

import asyncio
from typing import Sequence

import pytest

from app.v2.canon import (
    Character,
    CharacterRole,
    Constraints,
    Motif,
    MotifStatus,
    Premise,
    Promise,
    PromiseStatus,
    StoryModel,
    TimelineEvent,
    blocking,
)
from app.v2.llm import FakeStructuredLLM
from app.v2.plan import ChapterSpec
from app.v2.stages.reconcile import (
    AliasExtract,
    ChapterExtraction,
    CharacterFactExtract,
    ContradictionExtract,
    FlagKind,
    LedgerKind,
    LedgerObservation,
    PromotionKind,
    ReconcileFailed,
    TimelineExtract,
    WorldFactExtract,
    reconcile_chapter,
)

DRAFT = "Stettler stood at the edge of the Chrachen and did not look down."


# --------------------------------------------------------------------------------------------
# Fixtures / builders
# --------------------------------------------------------------------------------------------

def _canon() -> StoryModel:
    return StoryModel(
        premise=Premise(spark="s", central_question="q?", thesis="t", why_this_author="w"),
        author_id="duerrenmatt",
        characters={
            "stettler": Character(
                canonical_name="Dr. Konrad Stettler",
                aliases=["Stettler"],
                role=CharacterRole.PROTAGONIST,
                facts={"profession": "Amtsarzt"},
            ),
            "rutz": Character(
                canonical_name="Pfarrer Johannes Rutz",
                aliases=["Rutz", "der Pfarrer"],
                role=CharacterRole.SUPPORTING,
                facts={"office": "village priest"},
            ),
        },
        world_facts={"setting": "Lauenegg"},
        timeline=[
            TimelineEvent(id="t1", when="20y prior", event="Klara Vogel dies", involves=["stettler"], order=1)
        ],
        motifs=[Motif(id="formula_echo", desc="the phrase recurs identically", setup_ch=1, payoff_ch=3)],
        promises=[Promise(id="berta_question", desc="Berta's unanswered question", made_ch=1, kept_ch=3)],
        constraints=Constraints(language="de", chapter_count=5),
    )


def _spec(
    *,
    chapter: int = 3,
    setups: Sequence[str] = (),
    payoffs: Sequence[str] = (),
    promises_made: Sequence[str] = (),
    promises_kept: Sequence[str] = (),
) -> ChapterSpec:
    return ChapterSpec(
        chapter=chapter,
        title="Die Formel",
        purpose="Stettler signs the second certificate.",
        pov_character_id="stettler",
        present_character_ids=["stettler", "rutz"],
        advances_beats=[],
        setups=list(setups),
        payoffs=list(payoffs),
        promises_made=list(promises_made),
        promises_kept=list(promises_kept),
        entry_state=[],
        exit_state=[],
        scenes=[],
    )


def _extraction(
    *,
    character_facts: Sequence[CharacterFactExtract] = (),
    aliases: Sequence[AliasExtract] = (),
    world_facts: Sequence[WorldFactExtract] = (),
    timeline: Sequence[TimelineExtract] = (),
    contradictions: Sequence[ContradictionExtract] = (),
    ledger: Sequence[LedgerObservation] = (),
) -> ChapterExtraction:
    return ChapterExtraction(
        character_facts=list(character_facts),
        aliases=list(aliases),
        world_facts=list(world_facts),
        timeline=list(timeline),
        contradictions=list(contradictions),
        ledger=list(ledger),
    )


def _run(extraction: ChapterExtraction, canon: StoryModel, spec: ChapterSpec, **kwargs):
    llm = FakeStructuredLLM(responses=[extraction])
    result = asyncio.run(
        reconcile_chapter(
            chapter=spec.chapter, draft_text=DRAFT, canon=canon, spec=spec, llm=llm, **kwargs
        )
    )
    return result, llm


def _only(items):
    assert len(items) == 1, f"expected exactly one, got {items}"
    return items[0]


# --------------------------------------------------------------------------------------------
# Facts: new / consistent / contradiction
# --------------------------------------------------------------------------------------------

def test_a_new_fact_about_an_existing_character_is_promoted():
    canon = _canon()
    extraction = _extraction(character_facts=[
        CharacterFactExtract(
            character_id="stettler", surface_name="Stettler", key="Injury",
            value="a scar across the left hand", evidence="die Narbe an der linken Hand",
        )
    ])

    result, _ = _run(extraction, canon, _spec())

    assert result.canon.characters["stettler"].facts["injury"] == "a scar across the left hand"
    assert result.canon.characters["stettler"].facts["profession"] == "Amtsarzt"  # untouched
    promotion = _only(result.promoted)
    assert promotion.kind is PromotionKind.CHARACTER_FACT and promotion.ref == "stettler.injury"
    assert result.flagged == []
    assert result.is_valid


def test_a_fact_that_contradicts_canon_is_flagged_and_canon_is_unchanged():
    """The v1 death: the guardian wrote the prose's Rutz over canon's (F10) and it propagated."""
    canon = _canon()
    extraction = _extraction(character_facts=[
        CharacterFactExtract(
            character_id="rutz", surface_name="Rutz", key="office",
            value="local creditor the dead man owed money",
            evidence="der Rutz, dem der Tote Geld geschuldet hatte",
        )
    ])

    result, _ = _run(extraction, canon, _spec())

    assert result.canon.characters["rutz"].facts["office"] == "village priest"
    assert canon.characters["rutz"].facts["office"] == "village priest"  # the input canon is never touched
    assert result.promoted == []
    flag = _only(result.flagged)
    assert flag.kind is FlagKind.CONTRADICTION and flag.ref == "rutz.office"
    assert flag.canon_says == "village priest"
    assert "creditor" in flag.prose_says
    assert result.is_valid  # flagging IS the resolution here; it is not a stage failure


def test_a_fact_canon_already_states_is_ignored_not_duplicated():
    canon = _canon()
    extraction = _extraction(character_facts=[
        CharacterFactExtract(
            character_id="stettler", surface_name="Dr. Konrad Stettler", key="profession",
            value="Amtsarzt", evidence="der Amtsarzt unterschrieb",
        )
    ])

    result, _ = _run(extraction, canon, _spec())

    assert result.canon.characters["stettler"].facts == {"profession": "Amtsarzt"}
    assert result.promoted == []
    assert result.flagged == []


def test_a_contradiction_the_extractor_reports_is_flagged_verbatim():
    """The extractor is told to report conflicts, not resolve them — we keep both sides on record."""
    canon = _canon()
    extraction = _extraction(contradictions=[
        ContradictionExtract(
            canon_ref="t1", canon_says="Klara Vogel dies", prose_says="Anna Vogel dies of poisoning",
            evidence="Anna Vogel, vergiftet",
        )
    ])

    result, _ = _run(extraction, canon, _spec())

    flag = _only(result.flagged)
    assert flag.kind is FlagKind.CONTRADICTION and flag.ref == "t1"
    assert flag.canon_says == "Klara Vogel dies" and "poisoning" in flag.prose_says
    assert result.canon.timeline == canon.timeline


# --------------------------------------------------------------------------------------------
# Names: the F7/F10 fragmentation guard
# --------------------------------------------------------------------------------------------

def test_a_genuinely_new_alias_is_promoted_onto_the_right_character():
    canon = _canon()
    extraction = _extraction(aliases=[
        AliasExtract(character_id="stettler", alias="der Amtsarzt", evidence="der Amtsarzt schwieg")
    ])

    result, _ = _run(extraction, canon, _spec())

    assert result.canon.resolve_name("der Amtsarzt") == "stettler"
    assert "der Amtsarzt" in result.canon.characters["stettler"].aliases
    assert _only(result.promoted).kind is PromotionKind.ALIAS
    assert result.is_valid


def test_an_alias_owned_by_another_character_is_flagged_and_not_promoted():
    """Attaching 'der Pfarrer' to Stettler is how one character becomes two (F7)."""
    canon = _canon()
    extraction = _extraction(aliases=[
        AliasExtract(character_id="stettler", alias="der Pfarrer", evidence="der Pfarrer nickte")
    ])

    result, _ = _run(extraction, canon, _spec())

    assert result.promoted == []
    assert "der Pfarrer" not in result.canon.characters["stettler"].aliases
    assert result.canon.resolve_name("der Pfarrer") == "rutz"
    flag = _only(result.flagged)
    assert flag.kind is FlagKind.ALIAS_COLLISION and flag.ref == "stettler"
    assert result.is_valid  # canon stayed clean precisely BECAUSE we refused the alias


def test_an_unknown_surface_name_is_flagged_as_drift():
    canon = _canon()
    extraction = _extraction(character_facts=[
        CharacterFactExtract(
            character_id="rutz", surface_name="Vikar Brunner", key="age", value="sixty",
            evidence="Vikar Brunner, sechzig",
        )
    ])

    result, _ = _run(extraction, canon, _spec())

    assert result.canon.characters["rutz"].facts["age"] == "sixty"  # the fact itself is new and fine
    assert _only(result.flagged).kind is FlagKind.NAME_DRIFT


def test_a_fact_attributed_to_an_unknown_character_is_flagged_not_invented():
    canon = _canon()
    extraction = _extraction(character_facts=[
        CharacterFactExtract(
            character_id="der_wirt", surface_name="der Wirt", key="profession",
            value="innkeeper", evidence="der Wirt goss ein",
        )
    ])

    result, _ = _run(extraction, canon, _spec())

    assert set(result.canon.characters) == {"stettler", "rutz"}  # reconcile never creates a character
    assert _only(result.flagged).kind is FlagKind.UNKNOWN_CHARACTER


# --------------------------------------------------------------------------------------------
# World facts and timeline
# --------------------------------------------------------------------------------------------

def test_new_world_facts_and_timeline_events_are_promoted_with_normalised_ids():
    canon = _canon()
    extraction = _extraction(
        world_facts=[WorldFactExtract(
            key="Location: Chrachen", value="gorge south of the village", evidence="der Chrachen"
        )],
        timeline=[TimelineExtract(
            id="Ch3 Confession", when="ch3 night", event="Rutz hears Stettler's confession",
            involves=["Pfarrer Johannes Rutz", "stettler"], evidence="im Beichtstuhl",
        )],
    )

    result, _ = _run(extraction, canon, _spec())

    assert result.canon.world_facts["location_chrachen"] == "gorge south of the village"
    event = result.canon.timeline[-1]
    assert event.id == "ch3_confession"
    assert event.involves == ["rutz", "stettler"]  # a name reference resolved to an id
    assert event.order == 2
    assert {p.kind for p in result.promoted} == {PromotionKind.WORLD_FACT, PromotionKind.TIMELINE}
    assert result.is_valid


def test_an_event_already_on_the_timeline_is_not_appended_twice():
    """v1 appended timeline entries with no dedup at all, inflating every prompt after (F7)."""
    canon = _canon()
    extraction = _extraction(timeline=[TimelineExtract(
        id="ch3_recall", when="20y prior", event="Klara Vogel dies", involves=["stettler"], evidence="x"
    )])

    result, _ = _run(extraction, canon, _spec())

    assert [ev.id for ev in result.canon.timeline] == ["t1"]
    assert result.promoted == []


def test_an_event_with_a_dangling_reference_is_flagged_not_promoted():
    canon = _canon()
    extraction = _extraction(timeline=[TimelineExtract(
        id="ch3_meeting", when="ch3", event="Someone new arrives", involves=["der_wirt"], evidence="x"
    )])

    result, _ = _run(extraction, canon, _spec())

    assert [ev.id for ev in result.canon.timeline] == ["t1"]
    assert _only(result.flagged).kind is FlagKind.UNRESOLVED_REFERENCE
    assert result.is_valid  # a missing entry beats a canon with a broken reference


# --------------------------------------------------------------------------------------------
# The ledger — advanced only by what the prose actually did
# --------------------------------------------------------------------------------------------

def test_motif_advances_from_planned_to_setup_when_the_prose_plants_it():
    canon = _canon()
    extraction = _extraction(ledger=[LedgerObservation(
        id="formula_echo", kind=LedgerKind.MOTIF_SETUP, landed=True,
        evidence="'Herzversagen, vermutlich beim Sturz'",
    )])

    result, _ = _run(extraction, canon, _spec(chapter=1, setups=["formula_echo"]))

    assert result.canon.motifs[0].status is MotifStatus.SETUP
    update = _only(result.ledger_updates)
    assert (update.id, update.from_status, update.to_status) == ("formula_echo", "planned", "setup")
    assert result.flagged == []


def test_a_payoff_the_prose_never_delivered_is_flagged_and_does_not_advance():
    """This is what makes the ledger a measure of meaning rather than bookkeeping."""
    canon = _canon()
    canon.motifs[0].status = MotifStatus.SETUP
    extraction = _extraction(ledger=[LedgerObservation(
        id="formula_echo", kind=LedgerKind.MOTIF_PAYOFF, landed=False,
        evidence="the phrase never recurs; the scene ends before the certificate is signed",
    )])

    result, _ = _run(extraction, canon, _spec(chapter=3, payoffs=["formula_echo"]))

    assert result.canon.motifs[0].status is MotifStatus.SETUP
    assert result.ledger_updates == []
    flag = _only(result.flagged)
    assert flag.kind is FlagKind.LEDGER_MISSING and flag.ref == "formula_echo"


def test_a_payoff_with_no_observation_at_all_is_also_flagged():
    """Silence is not confirmation — an unreported assignment must never bump a status."""
    canon = _canon()
    canon.motifs[0].status = MotifStatus.SETUP

    result, _ = _run(_extraction(), canon, _spec(chapter=3, payoffs=["formula_echo"]))

    assert result.canon.motifs[0].status is MotifStatus.SETUP
    assert _only(result.flagged).kind is FlagKind.LEDGER_MISSING


def test_a_promise_moves_from_open_to_kept_when_the_prose_keeps_it():
    canon = _canon()
    extraction = _extraction(ledger=[LedgerObservation(
        id="berta_question", kind=LedgerKind.PROMISE_KEPT, landed=True,
        evidence="Berta bekommt ihre Antwort",
    )])

    result, _ = _run(extraction, canon, _spec(chapter=3, promises_kept=["berta_question"]))

    assert result.canon.promises[0].status is PromiseStatus.KEPT
    assert result.canon.promises[0].kept_ch == 3
    update = _only(result.ledger_updates)
    assert (update.from_status, update.to_status) == ("open", "kept")


def test_a_ledger_id_the_canon_does_not_have_is_flagged():
    canon = _canon()
    extraction = _extraction(ledger=[LedgerObservation(
        id="ghost_motif", kind=LedgerKind.MOTIF_SETUP, landed=True, evidence="x"
    )])

    result, _ = _run(extraction, canon, _spec(chapter=1, setups=["ghost_motif"]))

    assert result.ledger_updates == []
    assert _only(result.flagged).kind is FlagKind.LEDGER_UNKNOWN


# --------------------------------------------------------------------------------------------
# Validation and grounding
# --------------------------------------------------------------------------------------------

def test_strict_raises_rather_than_return_a_canon_that_does_not_validate():
    canon = _canon()
    canon.characters["doppel"] = Character(canonical_name="Rutz", role=CharacterRole.BACKGROUND)

    with pytest.raises(ReconcileFailed) as exc:
        _run(_extraction(), canon, _spec(), strict=True)

    assert any(i.code == "canon.name_collision" for i in exc.value.issues)


def test_without_strict_the_invalid_canon_comes_back_with_its_reason():
    canon = _canon()
    canon.characters["doppel"] = Character(canonical_name="Rutz", role=CharacterRole.BACKGROUND)

    result, _ = _run(_extraction(), canon, _spec(), strict=False)

    assert not result.is_valid
    assert any(i.code == "canon.name_collision" for i in blocking(result.issues))


def test_the_extraction_prompt_is_grounded_in_the_slice_and_names_the_ids_under_review():
    canon = _canon()
    spec = _spec(chapter=3, payoffs=["formula_echo"], promises_kept=["berta_question"])

    _, llm = _run(_extraction(ledger=[
        LedgerObservation(id="formula_echo", kind=LedgerKind.MOTIF_PAYOFF, landed=True, evidence="x"),
        LedgerObservation(id="berta_question", kind=LedgerKind.PROMISE_KEPT, landed=True, evidence="x"),
    ]), canon, spec)

    call = _only(llm.calls)
    assert call.schema == "ChapterExtraction" and call.model == "sonnet"  # one call, not two (F3)
    assert "Canon slice" in call.prompt
    assert "village priest" in call.prompt          # the slice's facts, in full
    assert "der Pfarrer" in call.prompt             # ...including alias lists
    assert "- characters: stettler, rutz" in call.prompt
    assert "motif_payoff [formula_echo]" in call.prompt
    assert "promise_kept [berta_question]" in call.prompt
    assert DRAFT in call.prompt
    # and the instruction that keeps prose from becoming truth
    assert "Do NOT resolve it" in call.prompt
    assert "CANON IS TRUTH" in (call.system or "")
