"""
Author profile loading and management.
"""

import os
from pathlib import Path
from typing import Dict, Optional, List

import yaml

from .schema import AuthorProfile


class AuthorLoader:
    """
    Loads and manages author profiles from YAML files.
    """

    def __init__(self, profiles_dir: Optional[str] = None):
        """
        Initialize the author loader.

        Args:
            profiles_dir: Path to profiles directory. Defaults to ./profiles
        """
        if profiles_dir is None:
            profiles_dir = os.path.join(os.path.dirname(__file__), "profiles")

        self.profiles_dir = Path(profiles_dir)
        self._cache: Dict[str, AuthorProfile] = {}

    def load(self, author_id: str) -> AuthorProfile:
        """
        Load an author profile by ID.

        Args:
            author_id: Author identifier (filename without .yaml)

        Returns:
            AuthorProfile instance

        Raises:
            FileNotFoundError: If profile doesn't exist
            ValueError: If profile is invalid
        """
        if author_id in self._cache:
            return self._cache[author_id]

        profile_path = self.profiles_dir / f"{author_id}.yaml"
        if not profile_path.exists():
            raise FileNotFoundError(f"Author profile not found: {author_id}")

        with open(profile_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        try:
            profile = AuthorProfile(**data)
            self._cache[author_id] = profile
            return profile
        except Exception as e:
            raise ValueError(f"Invalid author profile {author_id}: {e}")

    def list_authors(self) -> List[Dict[str, str]]:
        """
        List all available authors.

        Returns:
            List of dicts with id, name, and language
        """
        authors = []
        for path in self.profiles_dir.glob("*.yaml"):
            if path.stem.startswith("_"):
                continue  # Skip templates

            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)

                metadata = data.get("metadata", {})
                authors.append({
                    "id": path.stem,
                    "name": metadata.get("name", path.stem),
                    "language": metadata.get("primary_language", "en")
                })
            except Exception:
                continue  # Skip invalid files

        return authors

    def get_style_guide(self, author_id: str) -> str:
        """Get condensed style guide for an author."""
        profile = self.load(author_id)
        return profile.get_style_guide()

    def get_philosophy(self, author_id: str) -> str:
        """Get philosophy summary for an author."""
        profile = self.load(author_id)
        return profile.get_philosophy_summary()

    def get_character_patterns(self, author_id: str) -> str:
        """Get character patterns for an author."""
        profile = self.load(author_id)
        return profile.get_character_patterns_summary()

    def get_critique_rubric(self, author_id: str) -> dict:
        """Get critique rubric for an author."""
        profile = self.load(author_id)
        return profile.critique_rubric.model_dump()

    def get_language(self, author_id: str) -> str:
        """Get the primary language for an author."""
        profile = self.load(author_id)
        return profile.metadata.primary_language

    def clear_cache(self) -> None:
        """Clear the profile cache."""
        self._cache.clear()

    def validate_profile(self, author_id: str) -> tuple[bool, Optional[str]]:
        """
        Validate an author profile.

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            profile = self.load(author_id)

            # Check required fields
            if not profile.metadata.primary_language:
                return False, "Missing primary_language in metadata"

            if not profile.philosophy.worldview:
                return False, "Missing worldview in philosophy"

            if not profile.language.sentence_patterns:
                return False, "Missing sentence_patterns in language"

            if not profile.critique_rubric.voice_markers:
                return False, "Missing voice_markers in critique_rubric"

            return True, None

        except FileNotFoundError:
            return False, f"Profile not found: {author_id}"
        except ValueError as e:
            return False, str(e)
