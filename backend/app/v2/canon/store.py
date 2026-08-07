"""
Load/save canon files with history versioning.

Files are the source of truth (DESIGN D1). Each novel keeps its canon at
`novels/<slug>/01_canon/story_model.json`, with an append-only `history/` of every accepted version.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Union

from .model import StoryModel

CANON_FILE = "story_model.json"
HISTORY_DIR = "history"

PathLike = Union[str, Path]


def load_canon(canon_dir: PathLike) -> StoryModel:
    """Load `story_model.json` from a canon directory."""
    path = Path(canon_dir) / CANON_FILE
    data = json.loads(path.read_text(encoding="utf-8"))
    return StoryModel.model_validate(data)


def save_canon(model: StoryModel, canon_dir: PathLike, snapshot: bool = True) -> Path:
    """
    Write the canon to `story_model.json`. When `snapshot`, also write an immutable
    `history/v<version>.json` so every accepted state is auditable and reversible.
    """
    canon_dir = Path(canon_dir)
    canon_dir.mkdir(parents=True, exist_ok=True)
    payload = model.model_dump_json(indent=2)

    path = canon_dir / CANON_FILE
    path.write_text(payload, encoding="utf-8")

    if snapshot:
        hist = canon_dir / HISTORY_DIR
        hist.mkdir(parents=True, exist_ok=True)
        (hist / f"v{model.version:04d}.json").write_text(payload, encoding="utf-8")

    return path


def commit_canon(model: StoryModel, canon_dir: PathLike) -> StoryModel:
    """
    Bump the version, save, and snapshot. Returns the model with the incremented version.

    Use this for every accepted canon mutation so `history/` records the full lineage.
    """
    bumped = model.model_copy(update={"version": model.version + 1})
    save_canon(bumped, canon_dir, snapshot=True)
    return bumped
