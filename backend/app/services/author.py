"""Author service for loading and managing author profiles."""

import os
from pathlib import Path
from typing import Optional

import yaml

from app.config import get_settings
from app.schemas.author import AuthorDetail, AuthorSummary

settings = get_settings()


class AuthorService:
    """Service for loading author profiles from YAML files."""

    def __init__(self, authors_dir: Optional[str] = None):
        self.authors_dir = Path(authors_dir or settings.authors_dir)
        self._cache: dict[str, dict] = {}

    def _load_author_file(self, author_id: str) -> Optional[dict]:
        """Load an author YAML file."""
        if author_id in self._cache:
            return self._cache[author_id]

        # Try both .yaml and .yml extensions
        for ext in [".yaml", ".yml"]:
            file_path = self.authors_dir / f"{author_id}{ext}"
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    data["id"] = author_id
                    self._cache[author_id] = data
                    return data

        return None

    def list_authors(self) -> list[AuthorSummary]:
        """List all available authors."""
        authors = []

        if not self.authors_dir.exists():
            return authors

        for file_path in self.authors_dir.iterdir():
            if file_path.suffix in [".yaml", ".yml"]:
                author_id = file_path.stem
                data = self._load_author_file(author_id)
                if data:
                    authors.append(
                        AuthorSummary(
                            id=author_id,
                            name=data.get("name", author_id),
                            lived=data.get("lived", "Unknown"),
                            nationality=data.get("nationality", "Unknown"),
                        )
                    )

        return sorted(authors, key=lambda a: a.name)

    def get_author(self, author_id: str) -> Optional[AuthorDetail]:
        """Get detailed author profile."""
        data = self._load_author_file(author_id)
        if not data:
            return None

        return AuthorDetail(
            id=author_id,
            name=data.get("name", author_id),
            lived=data.get("lived", "Unknown"),
            nationality=data.get("nationality", "Unknown"),
            philosophy=data.get("philosophy", {}),
            structure=data.get("structure", {}),
            characters=data.get("characters", {}),
            prose=data.get("prose", {}),
            themes=data.get("themes", []),
            examples=data.get("examples", []),
            influences=data.get("influences", []),
        )

    def get_author_prompt_context(self, author_id: str) -> Optional[str]:
        """Get author information formatted for LLM prompts."""
        author = self.get_author(author_id)
        if not author:
            return None

        context_parts = [
            f"# Author Style: {author.name}",
            f"Nationality: {author.nationality}",
            f"Active: {author.lived}",
            "",
        ]

        if author.philosophy:
            context_parts.append("## Writing Philosophy")
            for key, value in author.philosophy.items():
                context_parts.append(f"- {key.replace('_', ' ').title()}: {value}")
            context_parts.append("")

        if author.prose:
            context_parts.append("## Prose Style")
            for key, value in author.prose.items():
                if isinstance(value, list):
                    context_parts.append(f"- {key.replace('_', ' ').title()}: {', '.join(value)}")
                else:
                    context_parts.append(f"- {key.replace('_', ' ').title()}: {value}")
            context_parts.append("")

        if author.structure:
            context_parts.append("## Narrative Structure")
            for key, value in author.structure.items():
                context_parts.append(f"- {key.replace('_', ' ').title()}: {value}")
            context_parts.append("")

        if author.characters:
            context_parts.append("## Character Development")
            for key, value in author.characters.items():
                context_parts.append(f"- {key.replace('_', ' ').title()}: {value}")
            context_parts.append("")

        if author.themes:
            context_parts.append("## Common Themes")
            for theme in author.themes:
                context_parts.append(f"- {theme}")
            context_parts.append("")

        return "\n".join(context_parts)
