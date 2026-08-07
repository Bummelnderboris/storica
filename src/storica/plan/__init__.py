"""The plan: macro arc (stage 3) and just-in-time chapter specs (stage 4)."""

from .model import (
    Act,
    ArcBeat,
    ChapterSpec,
    MacroArc,
    MacroArcDraft,
    MotifDraft,
    PromiseDraft,
    SceneSpec,
    StateFact,
    TensionPoint,
    TurningPoint,
)
from .store import (
    chapter_spec_path,
    load_chapter_spec,
    load_chapter_spec_if_present,
    load_macro_arc,
    macro_arc_path,
    save_chapter_spec,
    save_macro_arc,
    specced_chapters,
)
from .validation import validate_chapter_spec, validate_continuity, validate_macro_arc_draft

__all__ = [
    "Act", "ArcBeat", "ChapterSpec", "MacroArc", "MacroArcDraft", "MotifDraft", "PromiseDraft",
    "SceneSpec", "StateFact", "TensionPoint", "TurningPoint",
    "load_macro_arc", "save_macro_arc", "macro_arc_path", "load_chapter_spec",
    "load_chapter_spec_if_present", "save_chapter_spec", "chapter_spec_path", "specced_chapters",
    "validate_macro_arc_draft", "validate_chapter_spec", "validate_continuity",
]
