"""
Story DNA schema - captures the essence of a story from the quiz.
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class SparkData(BaseModel):
    """The initial spark of inspiration."""
    spark_type: str = Field(..., description="Type: image, character, whatif, feeling")
    description: str = Field(..., description="Description of the spark")
    emotional_core: Optional[str] = None


class GenreData(BaseModel):
    """Genre and tone settings."""
    primary_genre: str
    subgenres: List[str] = []
    tone_dark_light: int = Field(50, ge=0, le=100)  # 0=dark, 100=light
    tone_serious_playful: int = Field(50, ge=0, le=100)  # 0=serious, 100=playful
    tone_slow_fast: int = Field(50, ge=0, le=100)  # 0=slow, 100=fast


class WorldData(BaseModel):
    """World and setting information."""
    time_period: str
    location: str
    world_type: str  # realistic, fantastical, scifi, etc.
    atmosphere_words: List[str] = []  # 3 atmosphere words
    special_rules: Optional[str] = None


class ProtagonistData(BaseModel):
    """Protagonist details."""
    archetype: str
    flaw: str
    want: str  # External desire
    need: str  # Internal need
    name_suggestion: Optional[str] = None


class AntagonistData(BaseModel):
    """Antagonist details."""
    type: str  # person, organization, nature, self, society
    description: str
    motivation: Optional[str] = None


class CharacterData(BaseModel):
    """Character ensemble."""
    protagonist: ProtagonistData
    antagonist: Optional[AntagonistData] = None
    ensemble_size: str = "small"  # small, medium, large
    ensemble_notes: Optional[str] = None


class ConflictData(BaseModel):
    """Central conflict and stakes."""
    central_question: str
    stakes_personal: str
    stakes_external: Optional[str] = None
    stakes_philosophical: Optional[str] = None


class StructureData(BaseModel):
    """Story structure preferences."""
    structure_type: str = "three_act"  # three_act, five_act, hero_journey, nonlinear
    target_words: int = Field(60000, ge=20000, le=150000)
    chapter_count: int = Field(12, ge=5, le=50)
    pacing: str = "balanced"  # slow_burn, balanced, fast_paced


class VoiceData(BaseModel):
    """Author voice and style."""
    emulate_author: Optional[str] = None  # Author ID to emulate
    custom_style: Optional[str] = None  # Custom style description
    pov: str = "third_limited"  # first, third_limited, third_omniscient
    tense: str = "past"  # past, present


class StoryDNA(BaseModel):
    """Complete Story DNA from quiz."""
    spark: SparkData
    genre: GenreData
    world: WorldData
    characters: CharacterData
    conflict: ConflictData
    structure: StructureData
    voice: VoiceData

    def to_seed_text(self) -> str:
        """Convert Story DNA to a seed text for generation."""
        parts = [
            f"# Story Seed",
            f"",
            f"## The Spark",
            f"Type: {self.spark.spark_type}",
            f"Description: {self.spark.description}",
        ]

        if self.spark.emotional_core:
            parts.append(f"Emotional Core: {self.spark.emotional_core}")

        parts.extend([
            f"",
            f"## Genre & Tone",
            f"Primary Genre: {self.genre.primary_genre}",
            f"Subgenres: {', '.join(self.genre.subgenres) if self.genre.subgenres else 'None'}",
            f"Tone: Dark/Light={self.genre.tone_dark_light}, Serious/Playful={self.genre.tone_serious_playful}, Pacing={self.genre.tone_slow_fast}",
            f"",
            f"## World & Setting",
            f"Time Period: {self.world.time_period}",
            f"Location: {self.world.location}",
            f"World Type: {self.world.world_type}",
            f"Atmosphere: {', '.join(self.world.atmosphere_words)}",
        ])

        if self.world.special_rules:
            parts.append(f"Special Rules: {self.world.special_rules}")

        parts.extend([
            f"",
            f"## Protagonist",
            f"Archetype: {self.characters.protagonist.archetype}",
            f"Fatal Flaw: {self.characters.protagonist.flaw}",
            f"External Want: {self.characters.protagonist.want}",
            f"Internal Need: {self.characters.protagonist.need}",
        ])

        if self.characters.antagonist:
            parts.extend([
                f"",
                f"## Antagonist",
                f"Type: {self.characters.antagonist.type}",
                f"Description: {self.characters.antagonist.description}",
            ])

        parts.extend([
            f"",
            f"## Central Conflict",
            f"Central Question: {self.conflict.central_question}",
            f"Personal Stakes: {self.conflict.stakes_personal}",
        ])

        if self.conflict.stakes_external:
            parts.append(f"External Stakes: {self.conflict.stakes_external}")
        if self.conflict.stakes_philosophical:
            parts.append(f"Philosophical Stakes: {self.conflict.stakes_philosophical}")

        parts.extend([
            f"",
            f"## Structure",
            f"Structure: {self.structure.structure_type}",
            f"Target Words: {self.structure.target_words}",
            f"Chapters: {self.structure.chapter_count}",
            f"Pacing: {self.structure.pacing}",
            f"",
            f"## Voice & Style",
            f"POV: {self.voice.pov}",
            f"Tense: {self.voice.tense}",
        ])

        if self.voice.emulate_author:
            parts.append(f"Emulate Author: {self.voice.emulate_author}")
        if self.voice.custom_style:
            parts.append(f"Custom Style: {self.voice.custom_style}")

        return "\n".join(parts)


class ProjectCreateWithDNA(BaseModel):
    """Project creation request with Story DNA."""
    name: str
    author_id: str
    story_dna: StoryDNA
