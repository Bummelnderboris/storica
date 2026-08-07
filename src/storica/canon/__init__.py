"""Canon: the single structured source of truth (schema + validation + file store)."""

from .model import (
    StoryModel,
    Character,
    CharacterArc,
    CharacterRole,
    Relationship,
    TimelineEvent,
    Motif,
    MotifStatus,
    Promise,
    PromiseStatus,
    Premise,
    Constraints,
)
from .validation import validate, blocking, is_valid, Issue, Severity
from .store import load_canon, save_canon, commit_canon
from .slice import canon_slice

__all__ = [
    "StoryModel", "Character", "CharacterArc", "CharacterRole", "Relationship",
    "TimelineEvent", "Motif", "MotifStatus", "Promise", "PromiseStatus", "Premise",
    "Constraints", "validate", "blocking", "is_valid", "Issue", "Severity",
    "load_canon", "save_canon", "commit_canon", "canon_slice",
]
