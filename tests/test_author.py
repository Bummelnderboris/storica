"""Tests for author profile loading."""

from pathlib import Path

import pytest

from litai.engines.author import AuthorEngine, AuthorProfile


@pytest.fixture
def authors_dir():
    """Get the authors directory."""
    return Path(__file__).parent.parent / "authors"


def test_list_authors(authors_dir):
    """Test listing available authors."""
    authors = AuthorEngine.list_authors(authors_dir)
    assert "duerrenmatt" in authors


def test_load_duerrenmatt(authors_dir):
    """Test loading Dürrenmatt profile."""
    engine = AuthorEngine(authors_dir, "duerrenmatt")
    profile = engine.get_profile()

    assert profile.name == "Friedrich Dürrenmatt"
    assert profile.nationality == "Swiss"
    assert "Justice" in profile.philosophy.central_obsession


def test_profile_to_prompt(authors_dir):
    """Test converting profile to prompt context."""
    engine = AuthorEngine(authors_dir, "duerrenmatt")
    profile = engine.get_profile()

    context = profile.to_prompt_context()

    assert "Friedrich Dürrenmatt" in context
    assert "Philosophical Core" in context
    assert "Prose Style" in context
