"""YAML Author Adapter - implements AuthorPort using YAML files."""

from pathlib import Path
from typing import Optional, List
import yaml

from ..core.ports.authors import AuthorPort
from ..core.domain import Author


class YAMLAuthorAdapter(AuthorPort):
    """
    Author adapter using YAML profile files.

    Loads author profiles from YAML files in a directory.
    """

    def __init__(self, profiles_dir: str):
        """
        Initialize with profiles directory.

        Args:
            profiles_dir: Path to directory containing author YAML files
        """
        self.profiles_dir = Path(profiles_dir)
        self._cache: dict[str, Author] = {}

    async def get_author(self, author_id: str) -> Optional[Author]:
        """Get an author profile by ID."""
        # Check cache
        if author_id in self._cache:
            return self._cache[author_id]

        # Look for file
        profile_path = self.profiles_dir / f"{author_id}.yaml"
        if not profile_path.exists():
            profile_path = self.profiles_dir / f"{author_id}.yml"
            if not profile_path.exists():
                return None

        # Load and parse
        try:
            with open(profile_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            author = self._parse_author(author_id, data)
            self._cache[author_id] = author
            return author

        except Exception as e:
            print(f"Error loading author {author_id}: {e}")
            return None

    async def list_authors(self) -> List[Author]:
        """List all available author profiles."""
        authors = []

        for path in self.profiles_dir.glob("*.yaml"):
            if path.stem.startswith("_"):  # Skip templates
                continue
            author = await self.get_author(path.stem)
            if author:
                authors.append(author)

        for path in self.profiles_dir.glob("*.yml"):
            if path.stem.startswith("_"):
                continue
            if path.stem not in self._cache:
                author = await self.get_author(path.stem)
                if author:
                    authors.append(author)

        return authors

    async def get_style_guide(self, author_id: str) -> Optional[str]:
        """Get the condensed style guide for prompts."""
        author = await self.get_author(author_id)
        if not author:
            return None
        return author.get_style_guide()

    async def get_critique_rubric(self, author_id: str) -> Optional[dict]:
        """Get the critique rubric for evaluating prose."""
        author = await self.get_author(author_id)
        if not author:
            return None
        return author.critique_rubric

    def _parse_author(self, author_id: str, data: dict) -> Author:
        """Parse YAML data into Author domain entity."""
        metadata = data.get("metadata", {})
        philosophy = data.get("philosophy", {})
        language = data.get("language", {})
        structure = data.get("structure", {})
        characters = data.get("characters", {})
        themes = data.get("themes", {})
        critique = data.get("critique_rubric", {})

        return Author(
            id=author_id,
            name=metadata.get("name", author_id.title()),
            language=metadata.get("primary_language", "en"),
            philosophy={
                "worldview": philosophy.get("worldview", ""),
                "central_obsession": philosophy.get("central_obsession", ""),
                "beliefs": philosophy.get("beliefs", {}),
                "topic_lenses": philosophy.get("topic_lenses", []),
            },
            style={
                "sentence_patterns": language.get("sentence_patterns", []),
                "vocabulary": language.get("vocabulary", ""),
                "register": language.get("register_level", ""),
                "markers": language.get("markers", []),
                "anti_patterns": language.get("anti_patterns", []),
                "dialogue_style": language.get("dialogue_style", ""),
            },
            patterns={
                "structure": {
                    "signature_pattern": structure.get("signature_pattern", ""),
                    "act_rhythm": structure.get("act_rhythm", ""),
                    "endings": structure.get("endings", ""),
                    "openings": structure.get("openings", ""),
                },
                "characters": {
                    "protagonist_patterns": characters.get("protagonist_patterns", []),
                    "antagonist_patterns": characters.get("antagonist_patterns", []),
                    "archetypes": characters.get("archetypes", {}),
                },
                "themes": {
                    "primary": themes.get("primary", []),
                    "secondary": themes.get("secondary", []),
                    "forbidden": themes.get("forbidden", []),
                },
            },
            critique_rubric={
                "voice_markers": critique.get("voice_markers", []),
                "thematic_alignment": critique.get("thematic_alignment", []),
                "red_flags": critique.get("red_flags", []),
                "weights": {
                    "voice": critique.get("weight_voice", 0.35),
                    "theme": critique.get("weight_theme", 0.25),
                    "structure": critique.get("weight_structure", 0.20),
                    "language": critique.get("weight_language", 0.20),
                },
            },
        )
