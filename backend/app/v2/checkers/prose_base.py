"""
The interface every prose checker implements (DESIGN §6).

Prose is checked by *several* independent readers at once — micro-sense, author-voice,
canon-consistency, intent — and the prose loop must be able to run them without knowing which is
which. One signature, one verdict type, so adding a checker in P5 is a list entry rather than a
change to the loop.

`scene` is present when the unit under review is a single scene and `None` when it is the whole
chapter: checkers run on the smallest meaningful unit so a problem is localised rather than
averaged away (the F8 fix).
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from ..authors import AuthorModel
from ..canon import StoryModel
from ..plan import ChapterSpec, SceneSpec
from .base import Verdict


@runtime_checkable
class ProseChecker(Protocol):
    """A fresh-context reader that judges prose against canon and returns a verdict."""

    name: str

    async def check_prose(
        self,
        *,
        prose: str,
        canon: StoryModel,
        spec: ChapterSpec,
        author: AuthorModel,
        scene: Optional[SceneSpec] = None,
    ) -> Verdict:
        """Judge one prose unit. Never rewrites; returns issues with `fix_hint`s."""
        ...
