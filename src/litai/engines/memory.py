"""Memory engine for Story Bible management."""

from typing import Any

from .author import AuthorProfile
from ..llm.client import LLMClient
from ..llm.prompts import PromptTemplates


class MemoryEngine:
    """Manages the Story Bible - the project's living memory."""

    def __init__(self, project):
        self.project = project

    def update_story_bible(
        self,
        chapter_num: int,
        chapter_content: str,
        blueprint: str,
        current_bible: dict[str, Any],
        llm_client: LLMClient,
        author_profile: AuthorProfile,
    ) -> dict[str, Any]:
        """Update story bible after a chapter is written."""
        prompt = PromptTemplates.story_bible_update(
            chapter_num=chapter_num,
            chapter_content=chapter_content,
            blueprint=blueprint,
            current_bible=current_bible,
        )

        response = llm_client.generate(prompt)

        # Parse the YAML response
        updates = self._parse_bible_updates(response)

        # Merge updates into current bible
        return self._merge_updates(current_bible, updates, chapter_num)

    def _parse_bible_updates(self, response: str) -> dict[str, Any]:
        """Parse LLM response into story bible updates."""
        import yaml

        # Extract YAML from response (may be wrapped in markdown)
        yaml_content = response

        if "```yaml" in response:
            start = response.find("```yaml") + 7
            end = response.find("```", start)
            yaml_content = response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            yaml_content = response[start:end].strip()

        try:
            return yaml.safe_load(yaml_content) or {}
        except yaml.YAMLError:
            # If parsing fails, return empty updates
            return {}

    def _merge_updates(
        self,
        current: dict[str, Any],
        updates: dict[str, Any],
        chapter_num: int,
    ) -> dict[str, Any]:
        """Merge updates into the current story bible."""
        result = current.copy()

        # Update metadata
        result["metadata"]["last_updated"] = f"chapter_{chapter_num}"
        if "word_count" in updates:
            result["metadata"]["word_count_so_far"] = updates.get("word_count", 0)

        # Merge characters
        if "characters" in updates:
            for char_id, char_data in updates["characters"].items():
                if char_id in result["characters"]:
                    # Update existing character
                    result["characters"][char_id].update(char_data)
                    result["characters"][char_id]["last_appearance"] = f"chapter_{chapter_num}"
                else:
                    # Add new character
                    result["characters"][char_id] = char_data
                    result["characters"][char_id]["introduced"] = f"chapter_{chapter_num}"

        # Merge locations
        if "locations" in updates:
            for loc_id, loc_data in updates["locations"].items():
                if loc_id in result["locations"]:
                    result["locations"][loc_id].update(loc_data)
                else:
                    result["locations"][loc_id] = loc_data
                    result["locations"][loc_id]["established"] = f"chapter_{chapter_num}"

        # Merge plot threads
        if "plot_threads" in updates:
            for thread_id, thread_data in updates["plot_threads"].items():
                if thread_id in result["plot_threads"]:
                    result["plot_threads"][thread_id].update(thread_data)
                else:
                    result["plot_threads"][thread_id] = thread_data
                    result["plot_threads"][thread_id]["introduced"] = f"chapter_{chapter_num}"

        # Add timeline entry
        if "timeline" in updates and updates["timeline"]:
            result["timeline"].extend(updates["timeline"])

        # Add consistency notes
        if "consistency_notes" in updates and updates["consistency_notes"]:
            result["consistency_notes"].extend(updates["consistency_notes"])

        # Add foreshadowing
        if "foreshadowing" in updates and updates["foreshadowing"]:
            if "planted" in updates["foreshadowing"]:
                result["foreshadowing"]["planted"].extend(updates["foreshadowing"]["planted"])

        return result

    def get_relevant_context(
        self,
        story_bible: dict[str, Any],
        chapter_num: int,
        blueprint: str,
    ) -> str:
        """Extract relevant story bible context for a chapter."""
        lines = ["## Story Context\n"]

        # Active characters mentioned in blueprint
        characters = story_bible.get("characters", {})
        if characters:
            lines.append("### Characters")
            for char_id, char_data in characters.items():
                if isinstance(char_data, dict):
                    name = char_data.get("full_name", char_id)
                    state = char_data.get("current_state", "")
                    lines.append(f"- **{name}**: {state}")
            lines.append("")

        # Active plot threads
        threads = story_bible.get("plot_threads", {})
        active_threads = {
            k: v for k, v in threads.items()
            if isinstance(v, dict) and v.get("status") in ["active", "introduced"]
        }
        if active_threads:
            lines.append("### Active Plot Threads")
            for thread_id, thread_data in active_threads.items():
                status = thread_data.get("current_state", "")
                lines.append(f"- **{thread_id}**: {status}")
            lines.append("")

        # Recent timeline
        timeline = story_bible.get("timeline", [])
        recent = [t for t in timeline if isinstance(t, dict)][-3:]
        if recent:
            lines.append("### Recent Events")
            for entry in recent:
                ch = entry.get("chapter", "?")
                events = entry.get("events", [])
                lines.append(f"- Chapter {ch}: {', '.join(events)}")
            lines.append("")

        # Consistency notes
        notes = story_bible.get("consistency_notes", [])
        if notes:
            lines.append("### Consistency Notes")
            for note in notes[-5:]:
                lines.append(f"- {note}")

        return "\n".join(lines)
