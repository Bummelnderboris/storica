"""Ports - abstract interfaces for external dependencies."""

from .llm import LLMPort
from .storage import StoragePort
from .events import EventPort
from .authors import AuthorPort

__all__ = [
    "LLMPort",
    "StoragePort",
    "EventPort",
    "AuthorPort",
]
