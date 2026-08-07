"""
Tests for the v2 canon core.

Run from the backend/ directory:
    .venv/bin/python -m pytest tests/ -q

Proves the deterministic validator catches the exact failure modes that sank v1
(name fragmentation F7/F10, dangling refs, ledger inconsistencies) and that the corrected
Der-Chrachen canon fixture is clean.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from storica.canon import (
    Character,
    CharacterRole,
    Constraints,
    Motif,
    MotifStatus,
    Relationship,
    StoryModel,
    blocking,
    commit_canon,
    is_valid,
    load_canon,
    save_canon,
    validate,
)

# repo root = .../storica ; this file = .../storica/tests/test_canon.py
REPO_ROOT = Path(__file__).resolve().parents[1]
DER_CHRACHEN_CANON = REPO_ROOT / "novels" / "der-chrachen" / "01_canon"


def _codes(issues):
    return {i.code for i in issues}


# --------------------------------------------------------------------------------------------
# The corrected reference canon must be clean
# --------------------------------------------------------------------------------------------

def test_reference_canon_loads_and_is_valid():
    model = load_canon(DER_CHRACHEN_CANON)
    issues = validate(model)
    assert blocking(issues) == [], f"reference canon has blocking issues: {[str(i) for i in issues]}"
    assert is_valid(model)
    # sanity: the fixture is the story we ran, with Rutz as ONE character (priest + creditor)
    assert model.resolve_name("Pfarrer Rutz") == "rutz"
    assert model.resolve_name("Rutz") == "rutz"
    assert model.characters["stettler"].role == CharacterRole.PROTAGONIST


# --------------------------------------------------------------------------------------------
# The v1 failure modes must be caught
# --------------------------------------------------------------------------------------------

def test_name_fragmentation_is_blocking():
    """The v1 Rutz/Stettler failure: the same name owned by two character ids."""
    model = StoryModel(
        characters={
            "rutz": Character(canonical_name="Pfarrer Johannes Rutz", aliases=["Rutz"],
                              role=CharacterRole.SUPPORTING),
            "rutz_creditor": Character(canonical_name="Rutz",  # collides with rutz's alias
                                       role=CharacterRole.BACKGROUND),
            "hero": Character(canonical_name="A", role=CharacterRole.PROTAGONIST),
        },
    )
    issues = validate(model)
    assert "canon.name_collision" in _codes(blocking(issues))
    assert not is_valid(model)


def test_dangling_relationship_is_blocking():
    model = StoryModel(
        characters={"hero": Character(canonical_name="Hero", role=CharacterRole.PROTAGONIST)},
        relationships=[Relationship(a="hero", b="ghost", type="knows")],  # ghost does not exist
    )
    assert "ref.relationship" in _codes(blocking(validate(model)))


def test_dangling_timeline_involve_is_blocking():
    from storica.canon import TimelineEvent

    model = StoryModel(
        characters={"hero": Character(canonical_name="Hero", role=CharacterRole.PROTAGONIST)},
        timeline=[TimelineEvent(id="t1", when="start", event="x", involves=["nobody"])],
    )
    assert "ref.timeline" in _codes(blocking(validate(model)))


def test_motif_payoff_before_setup_is_blocking():
    model = StoryModel(
        characters={"hero": Character(canonical_name="Hero", role=CharacterRole.PROTAGONIST)},
        motifs=[Motif(id="m1", desc="x", setup_ch=3, payoff_ch=1, status=MotifStatus.PLANNED)],
    )
    assert "motif.payoff_before_setup" in _codes(blocking(validate(model)))


def test_no_protagonist_is_warning_not_blocking():
    model = StoryModel(
        characters={"a": Character(canonical_name="A", role=CharacterRole.SUPPORTING)},
    )
    issues = validate(model)
    assert "cast.no_protagonist" in _codes(issues)
    assert blocking(issues) == []  # warning only — still valid


# --------------------------------------------------------------------------------------------
# Store: round-trip + versioned history
# --------------------------------------------------------------------------------------------

def test_roundtrip_save_load(tmp_path):
    model = load_canon(DER_CHRACHEN_CANON)
    save_canon(model, tmp_path, snapshot=False)
    reloaded = load_canon(tmp_path)
    assert reloaded == model


def test_commit_bumps_version_and_snapshots(tmp_path):
    model = load_canon(DER_CHRACHEN_CANON)
    v0 = model.version
    bumped = commit_canon(model, tmp_path)
    assert bumped.version == v0 + 1
    # both the live file and a history snapshot exist
    assert (tmp_path / "story_model.json").exists()
    assert (tmp_path / "history" / f"v{bumped.version:04d}.json").exists()
    # the live file reflects the bumped version
    on_disk = json.loads((tmp_path / "story_model.json").read_text())
    assert on_disk["version"] == v0 + 1


def test_strict_schema_rejects_unknown_field():
    with pytest.raises(Exception):
        StoryModel.model_validate({"characters": {}, "bogus_field": 1})
