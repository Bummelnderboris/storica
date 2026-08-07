"""
Draft files: `novels/<slug>/03_drafts/chNN.md` (DESIGN §3, stage 5).

Files are the source of truth (D1), and prose is the one artifact that genuinely is text — so it
lands as markdown a human can read, not as a JSON field. Chapters are written one at a time and
the directory is simply whatever has been drafted so far; there is no manifest to fall out of sync
with the files.

Deliberately dumb, and deliberately *not* a source of facts: a draft is never read back to learn
what is true about the story. That is canon's job (stage 6 reconciles the draft *into* canon), and
conflating the two is what let v1's bible ratchet in whatever the prose happened to say (F10).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Union

PathLike = Union[str, Path]

_DRAFT_RE = re.compile(r"^ch(\d+)\.md$")


def chapter_draft_path(drafts_dir: PathLike, chapter: int) -> Path:
    return Path(drafts_dir) / f"ch{chapter:02d}.md"


def save_chapter_draft(text: str, drafts_dir: PathLike, chapter: int) -> Path:
    path = chapter_draft_path(drafts_dir, chapter)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def load_chapter_draft(drafts_dir: PathLike, chapter: int) -> str:
    return chapter_draft_path(drafts_dir, chapter).read_text(encoding="utf-8")


def load_chapter_draft_if_present(drafts_dir: PathLike, chapter: int) -> Optional[str]:
    """Used to thread continuity: the previous chapter may not be drafted yet (or at all)."""
    path = chapter_draft_path(drafts_dir, chapter)
    return path.read_text(encoding="utf-8") if path.exists() else None


def drafted_chapters(drafts_dir: PathLike) -> List[int]:
    """Chapter numbers that already have a draft on disk, ascending."""
    directory = Path(drafts_dir)
    if not directory.exists():
        return []
    found = (_DRAFT_RE.match(p.name) for p in directory.iterdir())
    return sorted(int(m.group(1)) for m in found if m)
