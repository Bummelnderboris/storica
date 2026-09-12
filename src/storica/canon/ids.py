"""
Canon identity: how a free-text name becomes an id, and how two names are compared.

Both rules have to be the same everywhere or canon fragments. Stage 2 mints ids from the names the
model invented; stage 6 has to resolve the names the *prose* used back onto those same ids; and the
validator has to notice when two characters answer to one name. If those three disagree about what
counts as the same string, the same person becomes two characters — which is exactly the failure
(F7/F10) that stable ids and alias lists exist to prevent.

So the rules live here, once, and are deliberately dull: lowercase, collapse whitespace, and for
ids, reduce anything that is not `[a-z0-9]` to a single underscore.
"""

from __future__ import annotations

import re
from typing import Optional

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slug(value: str) -> str:
    """A stable canon id from arbitrary text: `"Anna-Maria Rutz"` → `"anna_maria_rutz"`."""
    return _NON_ALNUM.sub("_", value.strip().lower()).strip("_")


def norm(name: str) -> str:
    """A name flattened for comparison only — never stored, never shown."""
    return " ".join(name.strip().lower().split())


def chapter_unit(chapter: int) -> str:
    """
    The label a chapter is known by everywhere: `ch01`.

    The quarantine log, the decision log, the tracer, the checkers and `assembly` are joined on
    this string after the fact — by `run_novel` deciding what to skip and by a person reading
    `05_reports/`. One format, one place.
    """
    return f"ch{chapter:02d}"


def unit_label(chapter: int, scene_id: Optional[str] = None) -> str:
    """`ch01_s2` for a scene, `ch01` for a chapter (see `chapter_unit`)."""
    return chapter_unit(chapter) + (f"_{scene_id}" if scene_id else "")
