"""Tests for project management."""

import tempfile
from pathlib import Path

import pytest

from litai.core.project import Project, ProjectStage


@pytest.fixture
def temp_projects_dir():
    """Create a temporary projects directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_create_project(temp_projects_dir):
    """Test creating a new project."""
    project = Project.create(
        projects_dir=temp_projects_dir,
        name="test-novel",
        author="duerrenmatt",
        target_words=30000,
    )

    assert project.config.name == "test-novel"
    assert project.config.author == "duerrenmatt"
    assert project.config.target_words == 30000
    assert project.config.current_stage == ProjectStage.ESSENCE


def test_project_directory_structure(temp_projects_dir):
    """Test that project creates correct directory structure."""
    project = Project.create(
        projects_dir=temp_projects_dir,
        name="test-novel",
        author="duerrenmatt",
    )

    assert (project.path / "blueprint").is_dir()
    assert (project.path / "chapters").is_dir()
    assert (project.path / "final").is_dir()
    assert (project.path / "history").is_dir()
    assert (project.path / "project.yaml").is_file()
    assert (project.path / "story_bible.yaml").is_file()


def test_save_and_load_essence(temp_projects_dir):
    """Test saving and loading essence document."""
    project = Project.create(
        projects_dir=temp_projects_dir,
        name="test-novel",
        author="duerrenmatt",
    )

    essence_content = "# Essence Document\n\nTest content."
    project.save_essence(essence_content)

    loaded = project.get_essence()
    assert loaded == essence_content


def test_list_projects(temp_projects_dir):
    """Test listing projects."""
    Project.create(temp_projects_dir, "novel-1", "duerrenmatt")
    Project.create(temp_projects_dir, "novel-2", "duerrenmatt")

    projects = Project.list_all(temp_projects_dir)
    assert "novel-1" in projects
    assert "novel-2" in projects
