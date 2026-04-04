"""Story Bible - maintains narrative consistency across chapters."""

import json
from datetime import datetime
from typing import Optional, List, Dict

from .schema import (
    StoryBibleData,
    StoryBibleCharacter,
    StoryBibleLocation,
    StoryBibleEvent,
    StoryBibleObject,
    StoryBibleUpdate
)


class StoryBible:
    """
    Manages the story bible - a living document that tracks all
    story elements for consistency checking.
    """

    def __init__(self, data: Optional[StoryBibleData] = None):
        """Initialize with optional existing data."""
        self.data = data or StoryBibleData()

    @classmethod
    def from_json(cls, json_str: str) -> "StoryBible":
        """Create from JSON string."""
        if not json_str or json_str == "{}":
            return cls()

        data_dict = json.loads(json_str)
        data = StoryBibleData(**data_dict)
        return cls(data)

    def to_json(self) -> str:
        """Serialize to JSON."""
        return self.data.model_dump_json(indent=2)

    def to_prompt_summary(self, max_chars: int = 5000) -> str:
        """Generate a summary for use in prompts."""
        parts = []

        # Characters
        if self.data.characters:
            parts.append("## Characters")
            for name, char in self.data.characters.items():
                parts.append(f"- **{name}**: {char.description}")
                if char.relationships:
                    rels = ", ".join(f"{k}: {v}" for k, v in char.relationships.items())
                    parts.append(f"  Relationships: {rels}")

        # Locations
        if self.data.locations:
            parts.append("\n## Locations")
            for name, loc in self.data.locations.items():
                parts.append(f"- **{name}**: {loc.description}")

        # Recent Timeline
        if self.data.timeline:
            parts.append("\n## Recent Events")
            for event in self.data.timeline[-10:]:  # Last 10 events
                parts.append(f"- Ch.{event.chapter}: {event.description}")

        # Objects
        if self.data.objects:
            parts.append("\n## Significant Objects")
            for name, obj in self.data.objects.items():
                parts.append(f"- **{name}**: {obj.description}")

        # Established Facts
        if self.data.established_facts:
            parts.append("\n## Established Facts")
            for fact, value in list(self.data.established_facts.items())[:20]:
                parts.append(f"- {fact}: {value}")

        summary = "\n".join(parts)

        # Truncate if too long
        if len(summary) > max_chars:
            summary = summary[:max_chars-100] + "\n\n[... truncated for brevity ...]"

        return summary

    def apply_updates(self, updates: List[StoryBibleUpdate]) -> None:
        """Apply a list of updates from consistency checking."""
        for update in updates:
            self._apply_single_update(update)

        self.data.last_updated = datetime.utcnow()

    def _apply_single_update(self, update: StoryBibleUpdate) -> None:
        """Apply a single update."""
        category = update.category.lower()

        if category == "character":
            self._update_character(update)
        elif category == "location":
            self._update_location(update)
        elif category == "event":
            self._add_event(update)
        elif category == "object":
            self._update_object(update)
        elif category == "fact":
            self.data.established_facts[update.key] = update.value
        elif category == "foreshadowing":
            if update.value not in self.data.foreshadowing:
                self.data.foreshadowing.append(update.value)

    def _update_character(self, update: StoryBibleUpdate) -> None:
        """Update or create a character entry."""
        name = update.key

        if name in self.data.characters:
            char = self.data.characters[name]
            char.last_seen = update.chapter_introduced
            # Could parse update.value for additional info
        else:
            self.data.characters[name] = StoryBibleCharacter(
                name=name,
                description=update.value,
                first_appearance=update.chapter_introduced,
                last_seen=update.chapter_introduced
            )

    def _update_location(self, update: StoryBibleUpdate) -> None:
        """Update or create a location entry."""
        name = update.key

        if name not in self.data.locations:
            self.data.locations[name] = StoryBibleLocation(
                name=name,
                description=update.value,
                first_mentioned=update.chapter_introduced
            )

    def _add_event(self, update: StoryBibleUpdate) -> None:
        """Add a timeline event."""
        event = StoryBibleEvent(
            chapter=update.chapter_introduced,
            description=update.value
        )
        self.data.timeline.append(event)

    def _update_object(self, update: StoryBibleUpdate) -> None:
        """Update or create an object entry."""
        name = update.key

        if name not in self.data.objects:
            self.data.objects[name] = StoryBibleObject(
                name=name,
                description=update.value,
                first_mentioned=update.chapter_introduced
            )

    def get_character(self, name: str) -> Optional[StoryBibleCharacter]:
        """Get a character by name."""
        return self.data.characters.get(name)

    def get_location(self, name: str) -> Optional[StoryBibleLocation]:
        """Get a location by name."""
        return self.data.locations.get(name)

    def get_fact(self, key: str) -> Optional[str]:
        """Get an established fact."""
        return self.data.established_facts.get(key)

    def search(self, query: str) -> Dict[str, list]:
        """Search the story bible for a term."""
        query_lower = query.lower()
        results = {
            "characters": [],
            "locations": [],
            "objects": [],
            "facts": []
        }

        for name, char in self.data.characters.items():
            if query_lower in name.lower() or query_lower in char.description.lower():
                results["characters"].append(name)

        for name, loc in self.data.locations.items():
            if query_lower in name.lower() or query_lower in loc.description.lower():
                results["locations"].append(name)

        for name, obj in self.data.objects.items():
            if query_lower in name.lower() or query_lower in obj.description.lower():
                results["objects"].append(name)

        for key, value in self.data.established_facts.items():
            if query_lower in key.lower() or query_lower in value.lower():
                results["facts"].append(key)

        return results
