"""
The author model (DESIGN §5 stage 0).

The author is a **generative driver**, not a paint job (principle 6): their obsessions and
question-lines select *which story gets told*, so Conception needs them as prompt material, not
just the Voice checker. This loads `authors/<id>/` into one object with a renderable prompt block.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Union

import yaml

PathLike = Union[str, Path]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


@dataclass
class AuthorModel:
    id: str
    name: str
    language: str
    profile: dict          # parsed profile.yaml
    question_lines: str    # question_lines.md — the obsessions that drive conception
    nudges: str            # nudges.md — steer toward / away (voice)
    impression: str        # impression.md — what it feels like to read them

    @property
    def philosophy(self) -> dict:
        return self.profile.get("philosophy", {}) or {}

    @property
    def central_obsession(self) -> str:
        return str(self.philosophy.get("central_obsession", "")).strip()

    @property
    def worldview(self) -> str:
        return str(self.philosophy.get("worldview", "")).strip()

    def conception_block(self) -> str:
        """The author material Conception (stage 1) reasons with."""
        return f"""# Author: {self.name} ({self.id})

## Worldview
{self.worldview}

## Central obsession
{self.central_obsession}

## Question-lines (the questions this author keeps asking)
{self.question_lines}

## What it feels like to read them
{self.impression}"""

    def voice_block(self) -> str:
        """The author material voice-sensitive stages need (kept separate so it can be cached)."""
        return f"# Author voice: {self.name}\n\n{self.nudges}"


def load_author(author_id: str, authors_root: PathLike) -> AuthorModel:
    """Load `authors/<author_id>/` into an AuthorModel."""
    root = Path(authors_root) / author_id
    profile_path = root / "profile.yaml"
    if not profile_path.exists():
        raise FileNotFoundError(f"no author profile at {profile_path}")

    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
    meta = profile.get("metadata", {}) or {}

    return AuthorModel(
        id=author_id,
        name=meta.get("name", author_id),
        language=meta.get("primary_language", "en"),
        profile=profile,
        question_lines=_read(root / "question_lines.md"),
        nudges=_read(root / "nudges.md"),
        impression=_read(root / "impression.md"),
    )
