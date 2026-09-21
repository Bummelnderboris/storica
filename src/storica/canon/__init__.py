"""Canon: the single structured source of truth (schema + validation + file store)."""

from .model import (
    StoryModel,
    Character,
    CharacterArc,
    CharacterRole,
    Relationship,
    TimelineEvent,
    Awareness,
    Knowing,
    KnowledgeItem,
    Motif,
    MotifStatus,
    Promise,
    PromiseStatus,
    Premise,
    Constraints,
)
from .ids import chapter_unit, norm, slug, unit_label
from .validation import validate, blocking, is_valid, Issue, Severity
from .store import load_canon, save_canon, commit_canon
from .slice import canon_slice, unit_slice
from .invention import INVENTION_POLICY

__all__ = [
    "StoryModel", "Character", "CharacterArc", "CharacterRole", "Relationship",
    "TimelineEvent", "Awareness", "Knowing", "KnowledgeItem", "Motif", "MotifStatus", "Promise", "PromiseStatus", "Premise",
    "Constraints", "validate", "blocking", "is_valid", "Issue", "Severity",
    "load_canon", "save_canon", "commit_canon", "canon_slice", "unit_slice", "INVENTION_POLICY", "norm", "slug", "chapter_unit", "unit_label",
]
