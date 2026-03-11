"""Project management for LitAI."""

from enum import Enum
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel


class ProjectStage(str, Enum):
    """Stages in the novel generation pipeline."""

    ESSENCE = "essence"
    ARCHITECTURE = "architecture"
    BLUEPRINT = "blueprint"
    PROSE = "prose"
    POLISH = "polish"
    COMPLETE = "complete"


class ProjectConfig(BaseModel):
    """Project configuration stored in project.yaml."""

    name: str
    author: str
    target_words: int = 45000
    current_stage: ProjectStage = ProjectStage.ESSENCE
    current_chapter: int = 0
    total_chapters: int = 0
    seed: Optional[str] = None


class Project:
    """Manages a novel project."""

    def __init__(self, path: Path):
        self.path = path
        self.config_path = path / "project.yaml"
        self.config: Optional[ProjectConfig] = None

        if self.config_path.exists():
            self._load_config()

    def _load_config(self) -> None:
        """Load project configuration."""
        with open(self.config_path) as f:
            data = yaml.safe_load(f)
        self.config = ProjectConfig(**data)

    def save_config(self) -> None:
        """Save project configuration."""
        with open(self.config_path, "w") as f:
            yaml.dump(self.config.model_dump(), f, default_flow_style=False)

    @classmethod
    def create(
        cls,
        projects_dir: Path,
        name: str,
        author: str,
        target_words: int = 45000,
    ) -> "Project":
        """Create a new project."""
        project_path = projects_dir / name

        if project_path.exists():
            raise ValueError(f"Project '{name}' already exists")

        # Create directory structure
        project_path.mkdir(parents=True)
        (project_path / "blueprint").mkdir()
        (project_path / "chapters").mkdir()
        (project_path / "final").mkdir()
        (project_path / "history").mkdir()

        # Create config
        project = cls(project_path)
        project.config = ProjectConfig(
            name=name,
            author=author,
            target_words=target_words,
        )
        project.save_config()

        # Initialize empty story bible
        project.save_story_bible({
            "metadata": {
                "last_updated": None,
                "word_count_so_far": 0,
            },
            "characters": {},
            "locations": {},
            "plot_threads": {},
            "world_rules": {},
            "timeline": [],
            "foreshadowing": {"planted": []},
            "consistency_notes": [],
        })

        return project

    @classmethod
    def load(cls, projects_dir: Path, name: str) -> "Project":
        """Load an existing project."""
        project_path = projects_dir / name

        if not project_path.exists():
            raise ValueError(f"Project '{name}' not found")

        return cls(project_path)

    @classmethod
    def list_all(cls, projects_dir: Path) -> list[str]:
        """List all projects."""
        if not projects_dir.exists():
            return []

        return [
            p.name
            for p in projects_dir.iterdir()
            if p.is_dir() and (p / "project.yaml").exists()
        ]

    # File access methods

    def get_essence(self) -> Optional[str]:
        """Get essence document content."""
        path = self.path / "essence.md"
        return path.read_text() if path.exists() else None

    def save_essence(self, content: str) -> None:
        """Save essence document."""
        (self.path / "essence.md").write_text(content)
        self._save_history("essence.md")

    def get_architecture(self) -> Optional[str]:
        """Get architecture document content."""
        path = self.path / "architecture.md"
        return path.read_text() if path.exists() else None

    def save_architecture(self, content: str) -> None:
        """Save architecture document."""
        (self.path / "architecture.md").write_text(content)
        self._save_history("architecture.md")

    def get_blueprint(self, chapter: int) -> Optional[str]:
        """Get chapter blueprint content."""
        path = self.path / "blueprint" / f"chapter_{chapter:02d}.md"
        return path.read_text() if path.exists() else None

    def save_blueprint(self, chapter: int, content: str) -> None:
        """Save chapter blueprint."""
        path = self.path / "blueprint" / f"chapter_{chapter:02d}.md"
        path.write_text(content)
        self._save_history(f"blueprint/chapter_{chapter:02d}.md")

    def get_all_blueprints(self) -> dict[int, str]:
        """Get all chapter blueprints."""
        blueprints = {}
        blueprint_dir = self.path / "blueprint"

        for path in sorted(blueprint_dir.glob("chapter_*.md")):
            chapter_num = int(path.stem.split("_")[1])
            blueprints[chapter_num] = path.read_text()

        return blueprints

    def get_chapter(self, chapter: int) -> Optional[str]:
        """Get chapter prose content."""
        path = self.path / "chapters" / f"chapter_{chapter:02d}.md"
        return path.read_text() if path.exists() else None

    def save_chapter(self, chapter: int, content: str) -> None:
        """Save chapter prose."""
        path = self.path / "chapters" / f"chapter_{chapter:02d}.md"
        path.write_text(content)
        self._save_history(f"chapters/chapter_{chapter:02d}.md")

    def get_all_chapters(self) -> dict[int, str]:
        """Get all written chapters."""
        chapters = {}
        chapters_dir = self.path / "chapters"

        for path in sorted(chapters_dir.glob("chapter_*.md")):
            chapter_num = int(path.stem.split("_")[1])
            chapters[chapter_num] = path.read_text()

        return chapters

    def get_story_bible(self) -> dict[str, Any]:
        """Get story bible content."""
        path = self.path / "story_bible.yaml"
        if not path.exists():
            return {}
        with open(path) as f:
            return yaml.safe_load(f) or {}

    def save_story_bible(self, content: dict[str, Any]) -> None:
        """Save story bible."""
        with open(self.path / "story_bible.yaml", "w") as f:
            yaml.dump(content, f, default_flow_style=False, allow_unicode=True)

    def _save_history(self, filename: str) -> None:
        """Save a version snapshot to history."""
        import shutil
        from datetime import datetime

        source = self.path / filename
        if source.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest_name = f"{timestamp}_{filename.replace('/', '_')}"
            dest = self.path / "history" / dest_name
            shutil.copy(source, dest)

    def compile_novel(self) -> str:
        """Compile all chapters into a single document."""
        chapters = self.get_all_chapters()
        if not chapters:
            return ""

        lines = [f"# {self.config.name}\n"]
        lines.append(f"*In the style of {self.config.author}*\n\n---\n")

        for num in sorted(chapters.keys()):
            lines.append(chapters[num])
            lines.append("\n---\n")

        return "\n".join(lines)

    def save_final(self) -> Path:
        """Save the final compiled novel."""
        content = self.compile_novel()
        path = self.path / "final" / "novel.md"
        path.write_text(content)
        return path
