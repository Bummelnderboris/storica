"""
Tests for knowledge state — who knows what, when (canon primitive).

Why this exists at all: in a story built on a concealed secret, the plot *is* the distribution of
knowledge. v1 had no representation for it, so nothing stopped a writer having a character allude to
something they cannot know, and no checker could catch it. The rules under test are the ones that
make the distribution binding rather than decorative:

- absence means unaware (silence is never permission);
- 'suspects' is not 'knows';
- a false belief must say what is believed instead, or it cannot be written;
- the slice must state a character's ignorance explicitly, because an omission reads as
  "unspecified", and unspecified is what leaks.
"""

from __future__ import annotations

from storica.canon import (
    Awareness,
    Character,
    CharacterRole,
    KnowledgeItem,
    Knowing,
    StoryModel,
    TimelineEvent,
    blocking,
    canon_slice,
    validate,
)
from storica.stages.world_cast import (
    ConstraintsDraft,
    KnowingDraft,
    KnowledgeDraft,
    WorldCastDraft,
    draft_to_canon,
)
from storica.canon import Premise


def _canon(**kw) -> StoryModel:
    base = dict(
        characters={
            "stettler": Character(canonical_name="Dr. Konrad Stettler", role=CharacterRole.PROTAGONIST),
            "berta": Character(canonical_name="Berta Aebischer"),
            "marolf": Character(canonical_name="Landjäger Marolf"),
        },
        timeline=[TimelineEvent(id="t1", when="20y prior", event="the forgery", involves=["stettler"])],
    )
    base.update(kw)
    return StoryModel(**base)


def _forgery(holders) -> KnowledgeItem:
    return KnowledgeItem(
        id="k_forgery",
        fact="Stettler forged Klara Vogel's death certificate.",
        concerns=["stettler", "t1"],
        holders=holders,
    )


# --------------------------------------------------------------------------------------------
# Model semantics
# --------------------------------------------------------------------------------------------

def test_absent_character_is_unaware_not_unspecified():
    item = _forgery([Knowing(character_id="stettler", awareness=Awareness.KNOWS)])
    assert item.awareness_of("stettler") == Awareness.KNOWS
    assert item.awareness_of("marolf") == Awareness.UNAWARE  # never listed
    assert item.awareness_of("nobody_at_all") == Awareness.UNAWARE


def test_suspicion_is_not_knowledge():
    canon = _canon(knowledge=[_forgery([
        Knowing(character_id="stettler", awareness=Awareness.KNOWS),
        Knowing(character_id="berta", awareness=Awareness.SUSPECTS, since="ch2"),
    ])])
    assert canon.knows("stettler", "k_forgery") is True
    assert canon.knows("berta", "k_forgery") is False       # the whole point
    assert canon.knows("marolf", "k_forgery") is False
    assert canon.knows("stettler", "k_nonexistent") is False


def test_knowledge_for_pairs_every_item_with_this_character_s_state():
    canon = _canon(knowledge=[_forgery([Knowing(character_id="berta", awareness=Awareness.SUSPECTS)])])
    assert canon.knowledge_for("berta") == [(canon.knowledge[0], Awareness.SUSPECTS)]
    assert canon.knowledge_for("marolf") == [(canon.knowledge[0], Awareness.UNAWARE)]


# --------------------------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------------------------

def test_holder_must_be_a_real_character():
    canon = _canon(knowledge=[_forgery([Knowing(character_id="ghost", awareness=Awareness.KNOWS)])])
    codes = [i.code for i in blocking(validate(canon))]
    assert "ref.knowledge_holder" in codes


def test_a_character_cannot_hold_two_states_of_one_fact():
    canon = _canon(knowledge=[_forgery([
        Knowing(character_id="berta", awareness=Awareness.KNOWS),
        Knowing(character_id="berta", awareness=Awareness.UNAWARE),
    ])])
    assert "knowledge.dup_holder" in [i.code for i in blocking(validate(canon))]


def test_false_belief_must_say_what_is_believed_instead():
    unspecified = _canon(knowledge=[_forgery([
        Knowing(character_id="marolf", awareness=Awareness.BELIEVES_FALSE),
    ])])
    assert "knowledge.false_belief_unspecified" in [i.code for i in blocking(validate(unspecified))]

    specified = _canon(knowledge=[_forgery([
        Knowing(character_id="marolf", awareness=Awareness.BELIEVES_FALSE,
                instead="that Klara Vogel died of heart failure"),
    ])])
    assert not blocking(validate(specified))


def test_duplicate_knowledge_id_blocks():
    canon = _canon(knowledge=[_forgery([]), _forgery([])])
    assert "knowledge.dup_id" in [i.code for i in blocking(validate(canon))]


def test_empty_fact_blocks():
    canon = _canon(knowledge=[KnowledgeItem(id="k_empty", fact="   ")])
    assert "knowledge.empty" in [i.code for i in blocking(validate(canon))]


def test_dangling_concerns_and_odd_since_are_warnings_not_blocking():
    canon = _canon(knowledge=[KnowledgeItem(
        id="k_x",
        fact="something",
        concerns=["not_an_id"],
        holders=[Knowing(character_id="berta", awareness=Awareness.KNOWS, since="last winter")],
    )])
    issues = validate(canon)
    codes = [i.code for i in issues]
    assert "ref.knowledge_concerns" in codes
    assert "knowledge.since" in codes
    assert not blocking(issues)  # imperfect metadata must not stop a book


def test_timeline_id_and_chapter_token_are_both_accepted_since_values():
    canon = _canon(knowledge=[_forgery([
        Knowing(character_id="stettler", awareness=Awareness.KNOWS, since="t1"),
        Knowing(character_id="berta", awareness=Awareness.SUSPECTS, since="ch2"),
    ])])
    assert not [i for i in validate(canon) if i.code == "knowledge.since"]


# --------------------------------------------------------------------------------------------
# The slice — what actually reaches the writer
# --------------------------------------------------------------------------------------------

def test_slice_states_ignorance_explicitly_for_everyone_in_scene():
    canon = _canon(knowledge=[_forgery([
        Knowing(character_id="stettler", awareness=Awareness.KNOWS, since="t1"),
        Knowing(character_id="berta", awareness=Awareness.SUSPECTS, since="ch2"),
    ])])
    text = canon_slice(canon, character_ids=["stettler", "berta", "marolf"])

    assert "WHO KNOWS WHAT" in text
    assert "k_forgery" in text
    assert "stettler: knows (since t1)" in text
    assert "berta: suspects (since ch2)" in text
    # marolf holds nothing and is in scene: his ignorance must be stated, not left out
    assert "marolf: unaware" in text


def test_slice_names_offstage_holders_so_the_writer_knows_the_secret_is_not_contained():
    canon = _canon(knowledge=[_forgery([
        Knowing(character_id="stettler", awareness=Awareness.KNOWS),
        Knowing(character_id="marolf", awareness=Awareness.SUSPECTS),
    ])])
    text = canon_slice(canon, character_ids=["stettler", "berta"])
    assert "not in this unit: marolf" in text


def test_slice_renders_the_false_belief_itself():
    canon = _canon(knowledge=[_forgery([
        Knowing(character_id="marolf", awareness=Awareness.BELIEVES_FALSE,
                instead="that it was heart failure"),
    ])])
    text = canon_slice(canon, character_ids=["marolf"])
    assert "holds instead: that it was heart failure" in text


def test_slice_omits_the_section_entirely_when_there_is_no_knowledge():
    assert "WHO KNOWS WHAT" not in canon_slice(_canon(), character_ids=["stettler"])


def test_slice_skips_knowledge_that_touches_nobody_in_the_unit():
    canon = _canon(knowledge=[KnowledgeItem(
        id="k_elsewhere",
        fact="a fact about other people",
        concerns=["marolf"],
        holders=[Knowing(character_id="marolf", awareness=Awareness.KNOWS)],
    )])
    assert "k_elsewhere" not in canon_slice(canon, character_ids=["stettler", "berta"])


# --------------------------------------------------------------------------------------------
# Stage 2 produces it
# --------------------------------------------------------------------------------------------

def test_draft_to_canon_carries_knowledge_and_resolves_names_to_ids():
    draft = WorldCastDraft(
        characters=[],
        relationships=[],
        world_facts=[],
        timeline=[],
        knowledge=[KnowledgeDraft(
            id="K Forgery",                     # unslugged on purpose
            fact="Stettler forged the certificate.",
            concerns=["stettler"],
            holders=[KnowingDraft(
                character_id="stettler", awareness=Awareness.KNOWS, since="t1", instead=""
            )],
        )],
        constraints=ConstraintsDraft(language="de", forbidden=[], chapter_count=3),
    )

    canon = draft_to_canon(draft, premise=Premise(), author_id="duerrenmatt")

    assert len(canon.knowledge) == 1
    item = canon.knowledge[0]
    assert item.id == "k_forgery"               # slugified like every other id
    assert item.holders[0].awareness == Awareness.KNOWS
    assert item.holders[0].since == "t1"


# --------------------------------------------------------------------------------------------
# The slice as of a chapter: a scheduled shift is not yet a held fact
# --------------------------------------------------------------------------------------------

def _scheduled() -> StoryModel:
    return _canon(knowledge=[_forgery([
        Knowing(character_id="stettler", awareness=Awareness.KNOWS, since="t1"),
        Knowing(character_id="berta", awareness=Awareness.SUSPECTS, since="ch2"),
    ])])


def test_a_shift_scheduled_for_a_later_chapter_is_rendered_as_the_ignorance_it_still_is():
    """Chapter 1's writer was told 'berta: suspects (since ch2)' — a suspicion she did not hold yet."""
    text = canon_slice(_scheduled(), character_ids=["stettler", "berta"], as_of_chapter=1)
    assert "berta: unaware in this chapter (becomes 'suspects' in ch2 — not yet)" in text
    assert "stettler: knows (since t1)" in text


def test_a_shift_due_in_this_chapter_is_an_event_the_page_must_deliver():
    text = canon_slice(_scheduled(), character_ids=["berta"], as_of_chapter=2)
    assert "berta: unaware as this chapter opens; becomes 'suspects' DURING it" in text


def test_after_its_chapter_a_shift_is_simply_held():
    text = canon_slice(_scheduled(), character_ids=["berta"], as_of_chapter=3)
    assert "berta: suspects (since ch2)" in text


def test_without_a_chapter_the_whole_schedule_is_shown():
    """Planning stages see the book's schedule, not one chapter's moment in it."""
    text = canon_slice(_scheduled(), character_ids=["berta"])
    assert "berta: suspects (since ch2)" in text
