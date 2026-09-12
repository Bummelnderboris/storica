"""
The interface every prose checker implements (DESIGN §6).

Prose is checked by *several* independent readers at once — canon-consistency, micro-sense,
author-voice, vitality — and the prose loop must be able to run them without knowing which is
which. One signature, one verdict type, so adding a reader is a list entry in
`checkers/defaults.py` rather than a change to the loop.

`scene` is present when the unit under review is a single scene and `None` when it is the whole
chapter: checkers run on the smallest meaningful unit so a problem is localised rather than
averaged away (the F8 fix).
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from ..authors import AuthorModel
from ..canon import StoryModel, unit_slice, unit_label as _unit_label
from ..plan import ChapterSpec, SceneSpec
from .base import Checker, Verdict


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
        draw: int = 1,
    ) -> Verdict:
        """Judge one prose unit. Never rewrites; returns issues with `fix_hint`s."""
        ...


def unit_label(spec: ChapterSpec, scene: Optional[SceneSpec]) -> str:
    """The name a prose unit is known by everywhere; the rule is `canon.unit_label`."""
    return _unit_label(spec.chapter, scene.id if scene else None)


class ProseCheckerBase(Checker):
    """
    Shared machinery for the readers that judge prose against the full canon.

    `scene_slice` is the grounding rule from DESIGN §5 in one place: a unit is judged against
    exactly what it touches. A scene gets its own cast, so a person who wandered in from nowhere
    shows up as absent from the slice rather than being quietly covered by the chapter's wider
    roster; a chapter gets the whole chapter cast.

    Deliberately *not* shared: the header and the prompt each reader assembles. Those are the
    reader's question, and they should be free to diverge — a shared prompt template would make
    every rubric edit a negotiation with four other checkers.
    """

    def scene_slice(
        self, canon: StoryModel, spec: ChapterSpec, scene: Optional[SceneSpec]
    ) -> str:
        """The canon slice for one prose unit — the same one the writer had (`canon.unit_slice`)."""
        return unit_slice(canon, spec, scene)
