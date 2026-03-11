"""Prompt templates for LitAI."""

from typing import Any, Optional

from ..engines.author import AuthorProfile


class PromptTemplates:
    """Centralized prompt templates."""

    @staticmethod
    def essence(
        seed: str,
        author_profile: AuthorProfile,
        guidance: Optional[str] = None,
    ) -> str:
        """Generate prompt for essence document."""
        author_context = author_profile.to_prompt_context()

        prompt = f"""{author_context}

---

## Your Task

Create an Essence Document for a novel based on this seed idea:

**Seed:** {seed}

The Essence Document should explore how {author_profile.name} would approach this topic. Include:

1. **Philosophical Lens** - How would this author view this subject matter? What unique perspective would they bring?

2. **Central Question** - What fundamental question would drive the narrative?

3. **Thematic Territory** - What themes would the author explore? (List 3-5 themes)

4. **Emotional Core** - What is the emotional journey? What should readers feel?

Format your response as a markdown document starting with "# Essence Document"
"""

        if guidance:
            prompt += f"\n\n**Revision Guidance:** {guidance}"

        return prompt

    @staticmethod
    def architecture(
        essence: str,
        author_profile: AuthorProfile,
        target_words: int,
        guidance: Optional[str] = None,
    ) -> str:
        """Generate prompt for narrative architecture."""
        author_context = author_profile.to_prompt_context()

        # Calculate chapter count
        words_per_chapter = 2500
        chapter_count = max(10, target_words // words_per_chapter)

        prompt = f"""{author_context}

---

## Previous Stage Output

{essence}

---

## Your Task

Create a Narrative Architecture document that structures the novel according to {author_profile.name}'s patterns.

**Target Length:** ~{target_words:,} words ({chapter_count} chapters, ~{words_per_chapter} words each)

The Architecture should include:

1. **Structure Type** - Name and describe the structural pattern being used (based on the author's signature patterns)

2. **Act Breakdown** - Divide the novel into acts (typically 3), describing:
   - The core movement of each act
   - Key turning points
   - How each act ends (remember: {author_profile.structure.endings})

3. **Chapter Allocation** - List all {chapter_count} chapters with:
   - Chapter title
   - Which act it belongs to
   - One-sentence description of its purpose

4. **Philosophical Arc** - How does the central question evolve through the narrative?

5. **Target Specifications** - Word count targets and chapter breakdown

Format as a markdown document starting with "# Narrative Architecture"
"""

        if guidance:
            prompt += f"\n\n**Revision Guidance:** {guidance}"

        return prompt

    @staticmethod
    def blueprint(
        chapter_num: int,
        architecture: str,
        author_profile: AuthorProfile,
        previous_blueprints: dict[int, str],
        guidance: Optional[str] = None,
    ) -> str:
        """Generate prompt for chapter blueprint."""
        author_context = author_profile.to_prompt_context()

        # Include summaries of previous blueprints for continuity
        prev_context = ""
        if previous_blueprints:
            summaries = []
            for num in sorted(previous_blueprints.keys())[-3:]:  # Last 3 chapters
                # Extract just the first few lines as summary
                bp = previous_blueprints[num]
                lines = bp.split("\n")[:10]
                summaries.append(f"**Chapter {num}:**\n" + "\n".join(lines))
            prev_context = "\n\n---\n\n## Previous Chapter Blueprints\n\n" + "\n\n".join(summaries)

        prompt = f"""{author_context}

---

## Narrative Architecture

{architecture}
{prev_context}

---

## Your Task

Create a detailed blueprint for **Chapter {chapter_num}**.

The blueprint should include:

1. **Chapter Header**
   - Title
   - Position (Act, Chapter number)
   - Word target (~2,500 words)

2. **Purpose in Arc** - What role does this chapter play in the larger narrative?

3. **Scenes** - Break down into 2-4 scenes, each with:
   - Scene title and word target
   - Setting description
   - What happens (not dialogue, but action and movement)
   - POV and narrative approach
   - Emotional tone

4. **Characters Present** - Who appears and their role in this chapter

5. **Key Details to Establish** - Specific facts, objects, or revelations that must be included

6. **Tone** - How should this chapter feel? Reference {author_profile.name}'s style.

7. **Continuity Notes** - What must connect to previous/future chapters?

Format as markdown starting with "# Chapter {chapter_num}:"
"""

        if guidance:
            prompt += f"\n\n**Revision Guidance:** {guidance}"

        return prompt

    @staticmethod
    def chapter(
        chapter_num: int,
        blueprint: str,
        author_profile: AuthorProfile,
        story_bible: dict[str, Any],
        previous_chapters: dict[int, str],
        guidance: Optional[str] = None,
    ) -> str:
        """Generate prompt for chapter prose."""
        author_context = author_profile.to_prompt_context()

        # Build story context from bible
        bible_context = PromptTemplates._build_bible_context(story_bible)

        # Get previous chapter ending for continuity
        prev_ending = ""
        if chapter_num > 1 and (chapter_num - 1) in previous_chapters:
            prev_chapter = previous_chapters[chapter_num - 1]
            # Get last 500 characters
            prev_ending = f"\n\n## Previous Chapter Ending\n\n...{prev_chapter[-500:]}"

        prompt = f"""{author_context}

---

## Chapter Blueprint

{blueprint}

---

{bible_context}
{prev_ending}

---

## Your Task

Write the complete prose for this chapter in {author_profile.name}'s voice.

**Critical Requirements:**
- Target: ~2,500 words
- Maintain the author's distinctive style throughout
- Follow the blueprint's scene structure
- Ensure continuity with previous chapters
- Apply the tone specified in the blueprint

**Style Reminders:**
- {author_profile.prose.tone}
- {author_profile.prose.sentence_rhythm}
- Avoid: {', '.join(author_profile.prose.avoid)}

Write the chapter now. Start with "# Chapter {chapter_num}:" followed by the chapter title, then the prose.
"""

        if guidance:
            prompt += f"\n\n**Revision Guidance:** {guidance}"

        return prompt

    @staticmethod
    def _build_bible_context(story_bible: dict[str, Any]) -> str:
        """Build context string from story bible."""
        lines = ["## Story Context"]

        # Characters
        characters = story_bible.get("characters", {})
        if characters:
            lines.append("\n### Active Characters")
            for char_id, data in list(characters.items())[:5]:
                if isinstance(data, dict):
                    name = data.get("full_name", char_id)
                    state = data.get("current_state", data.get("role", ""))
                    lines.append(f"- **{name}**: {state}")

        # Plot threads
        threads = story_bible.get("plot_threads", {})
        active = [
            (k, v) for k, v in threads.items()
            if isinstance(v, dict) and v.get("status") in ["active", "introduced"]
        ]
        if active:
            lines.append("\n### Active Plot Threads")
            for thread_id, data in active[:5]:
                state = data.get("current_state", data.get("details", ""))
                lines.append(f"- **{thread_id}**: {state}")

        # Consistency notes
        notes = story_bible.get("consistency_notes", [])
        if notes:
            lines.append("\n### Consistency Notes")
            for note in notes[-5:]:
                lines.append(f"- {note}")

        return "\n".join(lines)

    @staticmethod
    def story_bible_update(
        chapter_num: int,
        chapter_content: str,
        blueprint: str,
        current_bible: dict[str, Any],
    ) -> str:
        """Generate prompt for story bible update."""
        # Truncate chapter if too long
        chapter_excerpt = chapter_content[:3000] if len(chapter_content) > 3000 else chapter_content

        prompt = f"""You are a continuity editor maintaining a Story Bible for a novel in progress.

## Just Written: Chapter {chapter_num}

{chapter_excerpt}

---

## Chapter Blueprint

{blueprint}

---

## Current Story Bible State

Characters: {list(current_bible.get('characters', {}).keys())}
Locations: {list(current_bible.get('locations', {}).keys())}
Plot Threads: {list(current_bible.get('plot_threads', {}).keys())}

---

## Your Task

Extract new information from Chapter {chapter_num} to update the Story Bible. Return ONLY a YAML block with updates:

```yaml
characters:
  character_id:
    full_name: "Name"
    current_state: "Their state after this chapter"
    new_details:
      - "Any new details revealed"

locations:
  location_id:
    description: "If new location"
    details:
      - "New details"

plot_threads:
  thread_id:
    status: "active/resolved/background"
    current_state: "What happened to this thread"

timeline:
  - chapter: {chapter_num}
    time: "When this takes place"
    events:
      - "Key event 1"
      - "Key event 2"

consistency_notes:
  - "Any important details to maintain"

foreshadowing:
  planted:
    - chapter: {chapter_num}
      detail: "What was planted"
      payoff_planned: "When it should pay off"
```

Only include sections that have updates. Be concise but precise.
"""
        return prompt

    @staticmethod
    def consistency_check(
        chapters: dict[int, str],
        story_bible: dict[str, Any],
        author_profile: AuthorProfile,
    ) -> str:
        """Generate prompt for consistency checking."""
        # Build chapter summaries
        chapter_summaries = []
        for num in sorted(chapters.keys()):
            content = chapters[num]
            # Take first and last 200 chars as sample
            sample = content[:200] + "..." + content[-200:] if len(content) > 500 else content
            chapter_summaries.append(f"**Chapter {num}:**\n{sample}\n")

        summaries_text = "\n".join(chapter_summaries)

        prompt = f"""You are a continuity editor checking a completed novel draft for consistency issues.

## Author: {author_profile.name}

## Story Bible Summary

Characters: {list(story_bible.get('characters', {}).keys())}
Locations: {list(story_bible.get('locations', {}).keys())}
Consistency Notes: {story_bible.get('consistency_notes', [])}

## Chapter Samples

{summaries_text}

---

## Your Task

Check for consistency issues:

1. **Character Consistency** - Do character names, traits, and states remain consistent?
2. **Timeline Issues** - Are there temporal contradictions?
3. **Location Details** - Do location descriptions match?
4. **Plot Holes** - Are there unresolved threads or contradictions?
5. **Style Consistency** - Does the prose maintain {author_profile.name}'s voice throughout?

If you find issues, list them clearly with chapter references.
If no significant issues are found, respond with "No consistency issues found."
"""
        return prompt
