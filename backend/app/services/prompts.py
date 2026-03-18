"""Prompt templates for Storica generation pipeline."""

from typing import Any, Optional


class PromptTemplates:
    """Centralized prompt templates.

    All methods accept author_context as a pre-formatted string from
    AuthorService.get_prompt_context() rather than AuthorProfile objects.
    """

    @staticmethod
    def essence(
        seed: str,
        author_context: str,
        guidance: Optional[str] = None,
    ) -> str:
        """Generate prompt for essence document."""
        prompt = f"""{author_context}

---

## Your Task

Create an Essence Document for a novel based on this seed idea:

**Seed:** {seed}

The Essence Document should explore how this author would approach this topic. Include:

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
        author_context: str,
        target_words: int,
        guidance: Optional[str] = None,
    ) -> str:
        """Generate prompt for narrative architecture."""
        # Calculate chapter count
        words_per_chapter = 2500
        chapter_count = max(10, target_words // words_per_chapter)

        prompt = f"""{author_context}

---

## Previous Stage Output

{essence}

---

## Your Task

Create a Narrative Architecture document that structures the novel according to the author's patterns described above.

**Target Length:** ~{target_words:,} words ({chapter_count} chapters, ~{words_per_chapter} words each)

The Architecture should include:

1. **Structure Type** - Name and describe the structural pattern being used (based on the author's signature patterns)

2. **Act Breakdown** - Divide the novel into acts (typically 3), describing:
   - The core movement of each act
   - Key turning points
   - How each act ends (refer to the author's ending style in the profile above)

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
        author_context: str,
        previous_blueprints: dict[int, str],
        guidance: Optional[str] = None,
    ) -> str:
        """Generate prompt for chapter blueprint."""
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

6. **Tone** - How should this chapter feel? Reference the author's style from the profile above.

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
        author_context: str,
        story_bible: dict[str, Any],
        previous_chapters: dict[int, str],
        guidance: Optional[str] = None,
        characters_limit: int = 15,
        prev_ending_chars: int = 1500,
        validation_warnings: Optional[list[str]] = None,
    ) -> str:
        """Generate prompt for chapter prose."""
        # Build story context from bible
        bible_context = PromptTemplates._build_bible_context(story_bible, characters_limit)

        # Get previous chapter ending for continuity
        prev_ending = ""
        if chapter_num > 1 and (chapter_num - 1) in previous_chapters:
            prev_chapter = previous_chapters[chapter_num - 1]
            # Get last N characters for better continuity
            prev_ending = f"\n\n## Previous Chapter Ending\n\n...{prev_chapter[-prev_ending_chars:]}"

        # Build validation warnings section if any
        warnings_section = ""
        if validation_warnings:
            warnings_section = "\n\n## Pre-Validation Warnings\n"
            for warning in validation_warnings:
                warnings_section += f"- {warning}\n"

        prompt = f"""{author_context}

---

## Chapter Blueprint

{blueprint}

---

{bible_context}
{prev_ending}
{warnings_section}

---

## Your Task

Write the complete prose for this chapter in the author's voice as described in the profile above.

**Critical Requirements:**
- Target: ~2,500 words
- Maintain the author's distinctive style throughout (see Prose Style section in profile)
- Follow the blueprint's scene structure
- Ensure continuity with previous chapters
- Apply the tone specified in the blueprint

**Style Reminders:**
- Follow the sentence rhythm, vocabulary, and tone from the author profile
- Use the style markers listed in the profile
- Avoid the items listed under "Avoid" in the prose style section

Write the chapter now. Start with "# Chapter {chapter_num}:" followed by the chapter title, then the prose.
"""

        if guidance:
            prompt += f"\n\n**Revision Guidance:** {guidance}"

        return prompt

    @staticmethod
    def _build_bible_context(story_bible: dict[str, Any], characters_limit: int = 15) -> str:
        """Build context string from story bible."""
        lines = ["## Story Context"]

        # Characters
        characters = story_bible.get("characters", {})
        if characters:
            lines.append("\n### Active Characters")
            for char_id, data in list(characters.items())[:characters_limit]:
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
    def prevalidation(
        blueprint: str,
        story_bible: dict[str, Any],
        architecture: str,
    ) -> str:
        """Generate prompt for blueprint pre-validation against story bible."""
        # Extract known entities from story bible
        known_characters = list(story_bible.get("characters", {}).keys())
        known_locations = list(story_bible.get("locations", {}).keys())
        known_threads = list(story_bible.get("plot_threads", {}).keys())

        prompt = f"""You are a continuity editor validating a chapter blueprint before prose generation.

## Chapter Blueprint to Validate

{blueprint}

---

## Known Story Elements (from Story Bible)

### Known Characters
{', '.join(known_characters) if known_characters else '(none yet)'}

### Known Locations
{', '.join(known_locations) if known_locations else '(none yet)'}

### Known Plot Threads
{', '.join(known_threads) if known_threads else '(none yet)'}

---

## Narrative Architecture Reference

{architecture[:2000]}

---

## Your Task

Validate the blueprint against the story bible. Check for:

1. **Unknown Characters** - Characters mentioned in blueprint not in story bible
2. **Unknown Locations** - Locations mentioned that haven't been established
3. **Plot Thread Consistency** - Are referenced threads consistent with their current state?
4. **Continuity Conflicts** - Any contradictions with established facts

Return your validation as YAML:

```yaml
validation_status: "pass" | "warn" | "fail"

unknown_characters:
  - name: "Character Name"
    context: "How they appear in blueprint"
    recommendation: "add_to_bible" | "verify_name" | "potential_typo"

unknown_locations:
  - name: "Location Name"
    context: "How it appears in blueprint"
    recommendation: "add_to_bible" | "verify_name"

continuity_warnings:
  - element: "What element"
    issue: "Description of the issue"
    severity: "low" | "medium" | "high"

recommended_bible_additions:
  characters:
    character_id:
      full_name: "Name"
      role: "Role in story"
  locations:
    location_id:
      description: "Brief description"
```

Be conservative - only flag genuine concerns, not minor details.
"""
        return prompt

    @staticmethod
    def critique(
        draft: str,
        blueprint: str,
        author_context: str,
        story_bible: dict[str, Any],
    ) -> str:
        """Generate prompt for self-critique of draft chapter."""
        prompt = f"""You are a literary editor reviewing a draft chapter for quality and consistency.

## Author Being Emulated

{author_context}

---

## Chapter Blueprint (what was requested)

{blueprint}

---

## Draft Chapter (what was written)

{draft}

---

## Story Bible Context

Characters: {list(story_bible.get('characters', {}).keys())[:10]}
Active Plot Threads: {[k for k, v in story_bible.get('plot_threads', {}).items() if isinstance(v, dict) and v.get('status') in ['active', 'introduced']][:5]}

---

## Your Task

Critique this draft on four dimensions. Score each 1-10 and provide specific feedback.

Return your critique as YAML:

```yaml
scores:
  voice_fidelity: 7  # How well does it capture the author's voice?
  blueprint_adherence: 8  # Does it follow the blueprint's structure and scenes?
  continuity: 9  # Is it consistent with story bible and previous chapters?
  prose_quality: 7  # Overall prose quality (pacing, imagery, dialogue)

overall_score: 7.75  # Average of above

needs_revision: true  # true if overall_score < 7

revision_instructions:
  voice_issues:
    - "The dialogue feels too modern for this author's period style"
    - "Missing the characteristic short, punchy paragraphs"

  blueprint_gaps:
    - "Scene 2 from blueprint was skipped entirely"
    - "Key revelation about the letter wasn't included"

  continuity_problems:
    - "Character referred to as 'Sarah' but story bible says 'Sara'"
    - "Timeline inconsistency - this should be morning, not evening"

  prose_improvements:
    - "Opening paragraph is too slow - needs stronger hook"
    - "Action sequence in middle lacks tension"

strengths:
  - "Excellent character voice for the protagonist"
  - "Setting descriptions are atmospheric and evocative"
```

Be constructive but honest. The goal is quality iteration.
"""
        return prompt

    @staticmethod
    def polish(
        draft: str,
        critique_result: dict[str, Any],
        author_context: str,
        blueprint: str,
    ) -> str:
        """Generate prompt for polishing draft based on critique."""
        # Extract revision instructions from critique
        revision_instructions = critique_result.get("revision_instructions", {})
        voice_issues = revision_instructions.get("voice_issues", [])
        blueprint_gaps = revision_instructions.get("blueprint_gaps", [])
        continuity_problems = revision_instructions.get("continuity_problems", [])
        prose_improvements = revision_instructions.get("prose_improvements", [])
        strengths = critique_result.get("strengths", [])

        # Build revision guidance sections
        issues_text = ""
        if voice_issues:
            issues_text += "\n### Voice Issues to Fix\n"
            for issue in voice_issues:
                issues_text += f"- {issue}\n"

        if blueprint_gaps:
            issues_text += "\n### Blueprint Gaps to Address\n"
            for gap in blueprint_gaps:
                issues_text += f"- {gap}\n"

        if continuity_problems:
            issues_text += "\n### Continuity Problems to Correct\n"
            for problem in continuity_problems:
                issues_text += f"- {problem}\n"

        if prose_improvements:
            issues_text += "\n### Prose Improvements Needed\n"
            for improvement in prose_improvements:
                issues_text += f"- {improvement}\n"

        strengths_text = ""
        if strengths:
            strengths_text = "\n### Strengths to Preserve\n"
            for strength in strengths:
                strengths_text += f"- {strength}\n"

        prompt = f"""You are revising a chapter draft based on editorial feedback.

## Author Being Emulated

{author_context}

---

## Original Blueprint

{blueprint}

---

## Current Draft

{draft}

---

## Editorial Critique

**Overall Score:** {critique_result.get('overall_score', 'N/A')}/10
{issues_text}
{strengths_text}

---

## Your Task

Rewrite this chapter, addressing ALL the issues identified in the critique while preserving the strengths.

**Requirements:**
- Fix every voice, continuity, and prose issue listed above
- Ensure all blueprint scenes are included
- Maintain the target word count (~2,500 words)
- Preserve what's already working well

Write the complete revised chapter now. Start with the chapter heading.
"""
        return prompt

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
        author_context: str,
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

## Author Profile

{author_context}

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
5. **Style Consistency** - Does the prose maintain the author's voice throughout?

If you find issues, list them clearly with chapter references.
If no significant issues are found, respond with "No consistency issues found."
"""
        return prompt
