"""
Author profile schema definitions.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class AuthorMetadata(BaseModel):
    """Basic author information."""
    id: str
    name: str
    full_name: Optional[str] = None
    birth_year: Optional[int] = None
    death_year: Optional[int] = None
    nationality: Optional[str] = None
    primary_language: str = Field(..., description="Language the author wrote in (e.g., 'de', 'en')")
    notable_works: List[str] = []
    literary_movement: Optional[str] = None


class PhilosophySection(BaseModel):
    """Author's philosophical worldview."""
    worldview: str = Field(..., description="Core philosophical stance")
    central_obsession: str = Field(..., description="What the author returns to repeatedly")
    beliefs: Dict[str, str] = Field(default_factory=dict, description="Key beliefs about life, society, art")
    topic_lenses: List[str] = Field(default_factory=list, description="How they view story topics")


class DecisionPatterns(BaseModel):
    """How the author makes narrative decisions."""
    topic_approach: str = Field(..., description="How they approach story topics")
    plot_construction: str = Field(..., description="How they build plots")
    character_creation: str = Field(..., description="How they create characters")
    conflict_resolution: str = Field(default="", description="How they resolve conflicts")


class StructureSection(BaseModel):
    """Author's structural patterns."""
    signature_pattern: str = Field(..., description="Typical story structure")
    act_rhythm: str = Field(default="", description="Pacing across acts")
    chapter_patterns: str = Field(default="", description="Typical chapter structure")
    endings: str = Field(..., description="How they end stories")
    openings: str = Field(default="", description="How they begin stories")


class LanguageSection(BaseModel):
    """Author's linguistic style."""
    sentence_patterns: List[str] = Field(..., description="Typical sentence structures")
    vocabulary: str = Field(..., description="Vocabulary characteristics")
    register_level: str = Field(default="", description="Formal/informal, high/low")
    markers: List[str] = Field(default_factory=list, description="Distinctive style markers")
    anti_patterns: List[str] = Field(default_factory=list, description="What to avoid")
    dialogue_style: str = Field(default="", description="How characters speak")


class CharacterPatterns(BaseModel):
    """Author's character archetypes."""
    protagonist_patterns: List[str] = Field(..., description="Typical protagonist types")
    antagonist_patterns: List[str] = Field(default_factory=list, description="Typical antagonist types")
    archetypes: Dict[str, str] = Field(default_factory=dict, description="Recurring character types")
    relationships: str = Field(default="", description="How characters relate")


class ThemesSection(BaseModel):
    """Thematic concerns."""
    primary: List[str] = Field(..., description="Main thematic concerns")
    secondary: List[str] = Field(default_factory=list, description="Secondary themes")
    forbidden: List[str] = Field(default_factory=list, description="Themes to avoid")
    recurring_motifs: List[str] = Field(default_factory=list, description="Recurring symbols/motifs")


class AnnotatedExample(BaseModel):
    """An annotated example from the author's work."""
    text: str = Field(..., description="The example text in original language")
    source: str = Field(default="", description="Work it comes from")
    annotation: str = Field(default="", description="What makes this exemplary")
    category: str = Field(default="general", description="Type: opening, dialogue, description, etc.")


class CritiqueRubric(BaseModel):
    """Rubric for evaluating prose against author's style."""
    voice_markers: List[str] = Field(..., description="What indicates authentic voice")
    thematic_alignment: List[str] = Field(default_factory=list, description="How themes should manifest")
    red_flags: List[str] = Field(default_factory=list, description="Signs of inauthenticity")
    weight_voice: float = Field(default=0.35, ge=0, le=1)
    weight_theme: float = Field(default=0.25, ge=0, le=1)
    weight_structure: float = Field(default=0.20, ge=0, le=1)
    weight_language: float = Field(default=0.20, ge=0, le=1)


class AuthorProfile(BaseModel):
    """Complete author profile for style emulation."""

    metadata: AuthorMetadata
    philosophy: PhilosophySection
    decision_patterns: DecisionPatterns
    structure: StructureSection
    language: LanguageSection
    characters: CharacterPatterns
    themes: ThemesSection
    examples: List[AnnotatedExample] = Field(default_factory=list)
    critique_rubric: CritiqueRubric

    def get_style_guide(self) -> str:
        """Generate a condensed style guide for prompts."""
        guide_parts = [
            f"# Style Guide: {self.metadata.name}",
            f"\n## Language: {self.metadata.primary_language.upper()}",
            f"\n## Voice",
            f"- Worldview: {self.philosophy.worldview}",
            f"- Central obsession: {self.philosophy.central_obsession}",
            f"\n## Sentence Patterns",
        ]
        for pattern in self.language.sentence_patterns[:5]:
            guide_parts.append(f"- {pattern}")

        guide_parts.extend([
            f"\n## Vocabulary",
            f"{self.language.vocabulary}",
            f"\n## Style Markers",
        ])
        for marker in self.language.markers[:5]:
            guide_parts.append(f"- {marker}")

        guide_parts.extend([
            f"\n## Avoid",
        ])
        for anti in self.language.anti_patterns[:5]:
            guide_parts.append(f"- {anti}")

        return "\n".join(guide_parts)

    def get_philosophy_summary(self) -> str:
        """Generate philosophy summary for prompts."""
        parts = [
            f"# Philosophy of {self.metadata.name}",
            f"\n{self.philosophy.worldview}",
            f"\nCentral Obsession: {self.philosophy.central_obsession}",
            f"\n## Key Beliefs",
        ]
        for key, value in list(self.philosophy.beliefs.items())[:5]:
            parts.append(f"- {key}: {value}")

        return "\n".join(parts)

    def get_character_patterns_summary(self) -> str:
        """Generate character patterns summary for prompts."""
        parts = [
            f"# Character Patterns: {self.metadata.name}",
            f"\n## Protagonist Types",
        ]
        for pattern in self.characters.protagonist_patterns[:3]:
            parts.append(f"- {pattern}")

        parts.append("\n## Antagonist Types")
        for pattern in self.characters.antagonist_patterns[:3]:
            parts.append(f"- {pattern}")

        if self.characters.archetypes:
            parts.append("\n## Archetypes")
            for name, desc in list(self.characters.archetypes.items())[:5]:
                parts.append(f"- {name}: {desc}")

        return "\n".join(parts)

    def get_examples_by_category(self, category: str) -> List[AnnotatedExample]:
        """Get examples of a specific category."""
        return [ex for ex in self.examples if ex.category == category]
