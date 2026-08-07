"""
Plan files: `02_plan/macro_arc.json` and `02_plan/chapters/chNN.spec.json`.

Files are the source of truth (D1). Chapter specs are written one at a time, as they are
elaborated — the plan directory is a growing record of just-in-time decisions, not a frozen
mega-outline dumped up front (principle 2).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Optional, Union

from .model import ChapterSpec, MacroArc

PathLike = Union[str, Path]

MACRO_ARC_FILE = "macro_arc.json"
CHAPTERS_DIR = "chapters"

_SPEC_RE = re.compile(r"^ch(\d+)\.spec\.json$")


def macro_arc_path(plan_dir: PathLike) -> Path:
    return Path(plan_dir) / MACRO_ARC_FILE


def chapter_spec_path(plan_dir: PathLike, chapter: int) -> Path:
    return Path(plan_dir) / CHAPTERS_DIR / f"ch{chapter:02d}.spec.json"


def load_macro_arc(plan_dir: PathLike) -> MacroArc:
    return MacroArc.model_validate_json(macro_arc_path(plan_dir).read_text(encoding="utf-8"))


def save_macro_arc(arc: MacroArc, plan_dir: PathLike) -> Path:
    path = macro_arc_path(plan_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(arc.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_chapter_spec(plan_dir: PathLike, chapter: int) -> ChapterSpec:
    return ChapterSpec.model_validate_json(
        chapter_spec_path(plan_dir, chapter).read_text(encoding="utf-8")
    )


def save_chapter_spec(spec: ChapterSpec, plan_dir: PathLike) -> Path:
    path = chapter_spec_path(plan_dir, spec.chapter)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(spec.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_chapter_spec_if_present(plan_dir: PathLike, chapter: int) -> Optional[ChapterSpec]:
    """Used for JIT continuity: the previous chapter's spec may not exist yet (or at all)."""
    path = chapter_spec_path(plan_dir, chapter)
    return load_chapter_spec(plan_dir, chapter) if path.exists() else None


def specced_chapters(plan_dir: PathLike) -> List[int]:
    """Chapter numbers that already have a spec on disk, ascending."""
    directory = Path(plan_dir) / CHAPTERS_DIR
    if not directory.exists():
        return []
    found = (_SPEC_RE.match(p.name) for p in directory.iterdir())
    return sorted(int(m.group(1)) for m in found if m)
