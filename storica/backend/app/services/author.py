"""Author service for loading author profiles."""

from pathlib import Path
from typing import Optional

import yaml

from app.config import get_settings
from app.schemas.author import (
    AuthorCharacters,
    AuthorDetail,
    AuthorExamples,
    AuthorPhilosophy,
    AuthorProse,
    AuthorStructure,
    AuthorSummary,
)

settings = get_settings()


class AuthorService:
    """Service for loading and managing author profiles."""

    def __init__(self, authors_dir: Optional[Path] = None):
        self.authors_dir = authors_dir or settings.authors_dir
        self._cache: dict[str, dict] = {}

    def list_authors(self) -> list[AuthorSummary]:
        """List all available authors."""
        authors = []
        if not self.authors_dir.exists():
            return authors

        for author_dir in self.authors_dir.iterdir():
            if author_dir.is_dir():
                profile_path = author_dir / "profile.yaml"
                if profile_path.exists():
                    try:
                        data = self._load_profile(author_dir.name)
                        authors.append(
                            AuthorSummary(
                                id=author_dir.name,
                                name=data.get("name", author_dir.name),
                                lived=data.get("lived", "Unknown"),
                                nationality=data.get("nationality", "Unknown"),
                            )
                        )
                    except Exception:
                        continue
        return authors

    def _load_profile(self, author_id: str) -> dict:
        """Load an author profile from YAML."""
        if author_id in self._cache:
            return self._cache[author_id]

        profile_path = self.authors_dir / author_id / "profile.yaml"
        if not profile_path.exists():
            raise ValueError(f"Author profile not found: {author_id}")

        with open(profile_path) as f:
            data = yaml.safe_load(f)
            self._cache[author_id] = data
            return data

    def get_author(self, author_id: str) -> Optional[AuthorDetail]:
        """Get full author profile."""
        try:
            data = self._load_profile(author_id)
        except ValueError:
            return None

        return AuthorDetail(
            id=author_id,
            name=data.get("name", author_id),
            lived=data.get("lived", "Unknown"),
            nationality=data.get("nationality", "Unknown"),
            philosophy=AuthorPhilosophy(
                central_obsession=data["philosophy"]["central_obsession"],
                worldview=data["philosophy"]["worldview"],
                recurring_questions=data["philosophy"]["recurring_questions"],
                modern_lens=data["philosophy"]["modern_lens"],
            ),
            structure=AuthorStructure(
                signature_pattern=data["structure"]["signature_pattern"],
                description=data["structure"]["description"],
                act_rhythm=data["structure"]["act_rhythm"],
                endings=data["structure"]["endings"],
                favorite_devices=data["structure"]["favorite_devices"],
            ),
            characters=AuthorCharacters(
                protagonists=data["characters"]["protagonists"],
                antagonists=data["characters"]["antagonists"],
                dialogue_style=data["characters"]["dialogue_style"],
                archetypes=data["characters"]["archetypes"],
            ),
            prose=AuthorProse(
                sentence_rhythm=data["prose"]["sentence_rhythm"],
                vocabulary=data["prose"]["vocabulary"],
                tone=data["prose"]["tone"],
                markers=data["prose"]["markers"],
                avoid=data["prose"]["avoid"],
            ),
            themes=data.get("themes", {}),
            examples=AuthorExamples(
                openings=data["examples"]["openings"],
                dialogue=data["examples"]["dialogue"],
            ),
            influences=data.get("influences", []),
        )

    def get_prompt_context(self, author_id: str) -> Optional[str]:
        """Get author profile formatted for LLM prompts."""
        try:
            data = self._load_profile(author_id)
        except ValueError:
            return None

        lines = [
            f"# Author Profile: {data.get('name', author_id)}",
            f"Lived: {data.get('lived', 'Unknown')}",
            f"Nationality: {data.get('nationality', 'Unknown')}",
            "",
            "## Philosophy",
            f"Central Obsession: {data['philosophy']['central_obsession']}",
            f"Worldview: {data['philosophy']['worldview']}",
            "Recurring Questions:",
        ]
        for q in data["philosophy"]["recurring_questions"]:
            lines.append(f"  - {q}")

        lines.extend(
            [
                "",
                "## Narrative Structure",
                f"Signature Pattern: {data['structure']['signature_pattern']}",
                f"Description: {data['structure']['description']}",
                f"Endings: {data['structure']['endings']}",
                "Act Rhythm:",
            ]
        )
        for act in data["structure"]["act_rhythm"]:
            lines.append(f"  - {act}")

        lines.extend(
            [
                "",
                "## Characters",
                f"Protagonists: {data['characters']['protagonists']}",
                f"Antagonists: {data['characters']['antagonists']}",
                f"Dialogue Style: {data['characters']['dialogue_style']}",
                "Archetypes:",
            ]
        )
        for arch in data["characters"]["archetypes"]:
            lines.append(f"  - {arch}")

        lines.extend(
            [
                "",
                "## Prose Style",
                f"Sentence Rhythm: {data['prose']['sentence_rhythm']}",
                f"Vocabulary: {data['prose']['vocabulary']}",
                f"Tone: {data['prose']['tone']}",
                "Style Markers:",
            ]
        )
        for marker in data["prose"]["markers"]:
            lines.append(f"  - {marker}")

        lines.append("Avoid:")
        for avoid in data["prose"]["avoid"]:
            lines.append(f"  - {avoid}")

        if "themes" in data:
            lines.extend(["", "## Themes"])
            if "primary" in data["themes"]:
                lines.append("Primary:")
                for theme in data["themes"]["primary"]:
                    lines.append(f"  - {theme}")
            if "secondary" in data["themes"]:
                lines.append("Secondary:")
                for theme in data["themes"]["secondary"]:
                    lines.append(f"  - {theme}")

        if "examples" in data:
            lines.extend(["", "## Example Passages", "Openings:"])
            for opening in data["examples"]["openings"]:
                lines.append(f'  "{opening}"')
            lines.append("Dialogue:")
            for dialogue in data["examples"]["dialogue"]:
                lines.append(f'  "{dialogue}"')

        return "\n".join(lines)
