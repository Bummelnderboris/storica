"""Authors Port - interface for author profile access."""

from abc import ABC, abstractmethod
from typing import Optional, List
from ..domain import Author


class AuthorPort(ABC):
    """Abstract interface for author profile operations."""

    @abstractmethod
    async def get_author(self, author_id: str) -> Optional[Author]:
        """
        Get an author profile by ID.

        Args:
            author_id: The author identifier (e.g., "duerrenmatt", "hemingway")

        Returns:
            Author profile or None if not found
        """
        pass

    @abstractmethod
    async def list_authors(self) -> List[Author]:
        """
        List all available author profiles.

        Returns:
            List of available authors
        """
        pass

    @abstractmethod
    async def get_style_guide(self, author_id: str) -> Optional[str]:
        """
        Get the condensed style guide for prompts.

        Args:
            author_id: The author identifier

        Returns:
            Style guide text or None if author not found
        """
        pass

    @abstractmethod
    async def get_critique_rubric(self, author_id: str) -> Optional[dict]:
        """
        Get the critique rubric for evaluating prose.

        Args:
            author_id: The author identifier

        Returns:
            Critique rubric dict or None if author not found
        """
        pass
