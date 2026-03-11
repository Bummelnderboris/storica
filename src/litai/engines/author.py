"""Author profile management."""

from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel


class AuthorPhilosophy(BaseModel):
    """Author's philosophical core."""

    central_obsession: str
    worldview: str
    recurring_questions: list[str]
    modern_lens: dict[str, str] = {}


class AuthorStructure(BaseModel):
    """Author's structural patterns."""

    signature_pattern: str
    description: str
    act_rhythm: list[str]
    endings: str
    favorite_devices: list[str]


class AuthorCharacters(BaseModel):
    """Author's character philosophy."""

    protagonists: str
    antagonists: str
    dialogue_style: str
    archetypes: list[str]


class AuthorProse(BaseModel):
    """Author's prose style."""

    sentence_rhythm: str
    vocabulary: str
    tone: str
    markers: list[str]
    avoid: list[str]


class AuthorExamples(BaseModel):
    """Example passages in author's style."""

    openings: list[str] = []
    dialogue: list[str] = []


class AuthorProfile(BaseModel):
    """Complete author profile."""

    name: str
    lived: str
    nationality: str
    philosophy: AuthorPhilosophy
    structure: AuthorStructure
    characters: AuthorCharacters
    prose: AuthorProse
    themes: dict[str, list[str]]
    examples: AuthorExamples = AuthorExamples()
    influences: list[str] = []

    def to_prompt_context(self) -> str:
        """Convert profile to prompt-ready context."""
        lines = [
            f"## Author Voice: {self.name}",
            "",
            f"You are writing in the voice of {self.name} ({self.lived}), {self.nationality}.",
            "Internalize these principles:",
            "",
            "### Philosophical Core",
            f"Central Obsession: {self.philosophy.central_obsession}",
            f"Worldview: {self.philosophy.worldview}",
            "",
            "Recurring Questions:",
        ]

        for q in self.philosophy.recurring_questions:
            lines.append(f"- {q}")

        lines.extend([
            "",
            "### Structural Patterns",
            f"Signature Pattern: {self.structure.signature_pattern}",
            f"Description: {self.structure.description}",
            "",
            "Act Rhythm:",
        ])

        for step in self.structure.act_rhythm:
            lines.append(f"- {step}")

        lines.extend([
            "",
            f"Endings: {self.structure.endings}",
            "",
            "Favorite Devices:",
        ])

        for device in self.structure.favorite_devices:
            lines.append(f"- {device}")

        lines.extend([
            "",
            "### Character Philosophy",
            f"Protagonists: {self.characters.protagonists}",
            f"Antagonists: {self.characters.antagonists}",
            f"Dialogue Style: {self.characters.dialogue_style}",
            "",
            "### Prose Style",
            f"Sentence Rhythm: {self.prose.sentence_rhythm}",
            f"Vocabulary: {self.prose.vocabulary}",
            f"Tone: {self.prose.tone}",
            "",
            "Style Markers:",
        ])

        for marker in self.prose.markers:
            lines.append(f"- {marker}")

        lines.extend([
            "",
            "### What to Avoid",
        ])

        for avoid in self.prose.avoid:
            lines.append(f"- {avoid}")

        if self.examples.openings or self.examples.dialogue:
            lines.extend(["", "### Style Examples"])

            if self.examples.openings:
                lines.append("\nOpening Examples:")
                for ex in self.examples.openings:
                    lines.append(f'> "{ex}"')

            if self.examples.dialogue:
                lines.append("\nDialogue Examples:")
                for ex in self.examples.dialogue:
                    lines.append(f'> "{ex}"')

        return "\n".join(lines)


class AuthorEngine:
    """Manages author profiles."""

    def __init__(self, authors_dir: Path, author_name: str):
        self.authors_dir = authors_dir
        self.author_name = author_name
        self._profile: Optional[AuthorProfile] = None

    def get_profile(self) -> AuthorProfile:
        """Load and return the author profile."""
        if self._profile is None:
            self._profile = self._load_profile()
        return self._profile

    def _load_profile(self) -> AuthorProfile:
        """Load author profile from YAML."""
        profile_path = self.authors_dir / self.author_name / "profile.yaml"

        if not profile_path.exists():
            raise ValueError(f"Author profile not found: {self.author_name}")

        with open(profile_path) as f:
            data = yaml.safe_load(f)

        return AuthorProfile(**data)

    @classmethod
    def list_authors(cls, authors_dir: Path) -> list[str]:
        """List all available authors."""
        if not authors_dir.exists():
            return []

        return [
            d.name
            for d in authors_dir.iterdir()
            if d.is_dir() and (d / "profile.yaml").exists()
        ]

    @classmethod
    def get_author_summary(cls, authors_dir: Path, author_name: str) -> dict[str, Any]:
        """Get a brief summary of an author."""
        profile_path = authors_dir / author_name / "profile.yaml"

        if not profile_path.exists():
            raise ValueError(f"Author profile not found: {author_name}")

        with open(profile_path) as f:
            data = yaml.safe_load(f)

        return {
            "name": data.get("name", author_name),
            "lived": data.get("lived", "Unknown"),
            "nationality": data.get("nationality", "Unknown"),
            "central_obsession": data.get("philosophy", {}).get("central_obsession", ""),
            "themes": data.get("themes", {}).get("primary", []),
        }
