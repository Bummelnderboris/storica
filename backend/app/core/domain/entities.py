"""Domain entities - core business objects."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum


class PhaseType(str, Enum):
    """Pipeline phase types."""
    AUTHOR_LOADING = "author_loading"
    TOPIC_EXPLORATION = "topic_exploration"
    THESIS_DEVELOPMENT = "thesis_development"
    CHARACTER_DERIVATION = "character_derivation"
    STORY_ARCHITECTURE = "story_architecture"
    BLUEPRINT_PLANNING = "blueprint_planning"
    PROSE_GENERATION = "prose_generation"
    CONSISTENCY_CHECK = "consistency_check"


@dataclass
class StoryDNA:
    """The creative DNA of a story - user's vision."""
    spark: Dict[str, Any]
    genre: Dict[str, Any]
    world: Dict[str, Any]
    characters: Dict[str, Any]
    conflict: Dict[str, Any]
    structure: Dict[str, Any]
    voice: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "spark": self.spark,
            "genre": self.genre,
            "world": self.world,
            "characters": self.characters,
            "conflict": self.conflict,
            "structure": self.structure,
            "voice": self.voice,
        }


@dataclass
class Author:
    """Author profile for style emulation."""
    id: str
    name: str
    language: str  # Primary language (e.g., "de", "en")
    philosophy: Dict[str, Any]
    style: Dict[str, Any]
    patterns: Dict[str, Any]
    critique_rubric: Dict[str, Any]

    def get_style_guide(self) -> str:
        """Generate comprehensive style guide for prompts."""
        parts = [f"# Style Guide: {self.name}"]
        parts.append(f"Language: {self.language.upper()}")

        # Philosophy
        worldview = self.philosophy.get("worldview", "")
        obsession = self.philosophy.get("central_obsession", "")
        if worldview:
            parts.append(f"\n## Philosophy\n{worldview}")
        if obsession:
            parts.append(f"Central obsession: {obsession}")

        # Language & style
        style = self.style
        if style.get("vocabulary"):
            parts.append(f"\n## Vocabulary\n{style['vocabulary']}")
        if style.get("register"):
            parts.append(f"Register: {style['register']}")
        if style.get("sentence_patterns"):
            patterns = style["sentence_patterns"]
            if isinstance(patterns, list):
                parts.append("\n## Sentence Patterns")
                for p in patterns:
                    parts.append(f"- {p}")
            else:
                parts.append(f"\n## Sentence Patterns\n{patterns}")
        if style.get("dialogue_style"):
            parts.append(f"\n## Dialogue\n{style['dialogue_style']}")
        if style.get("markers"):
            parts.append("\n## Voice Markers")
            for m in style["markers"]:
                parts.append(f"- {m}")
        if style.get("anti_patterns"):
            parts.append("\n## NEVER DO (Anti-Patterns)")
            for a in style["anti_patterns"]:
                parts.append(f"- {a}")

        # Structural patterns
        structure = self.patterns.get("structure", {})
        if structure.get("signature_pattern"):
            parts.append(f"\n## Structure\n{structure['signature_pattern']}")
        if structure.get("openings"):
            parts.append(f"Openings: {structure['openings']}")
        if structure.get("endings"):
            parts.append(f"Endings: {structure['endings']}")

        # Thematic guidance
        themes = self.patterns.get("themes", {})
        if themes.get("primary"):
            parts.append("\n## Core Themes")
            for t in themes["primary"]:
                parts.append(f"- {t}")
        if themes.get("forbidden"):
            parts.append("\n## Forbidden Themes (AVOID)")
            for t in themes["forbidden"]:
                parts.append(f"- {t}")

        return "\n".join(parts)


@dataclass
class Chapter:
    """A chapter in the story."""
    number: int
    title: Optional[str] = None
    content: Optional[str] = None
    word_count: int = 0
    blueprint: Optional[Dict[str, Any]] = None
    critique_history: List[Dict[str, Any]] = field(default_factory=list)
    final_score: float = 0.0
    status: str = "pending"


@dataclass
class Project:
    """A story project."""
    id: int
    name: str
    user_id: int
    author_id: str
    story_dna: Optional[StoryDNA] = None
    target_words: int = 50000
    total_chapters: int = 10
    chapters: List[Chapter] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Generated artifacts
    topic_analysis: Optional[Dict[str, Any]] = None
    thesis: Optional[Dict[str, Any]] = None
    character_system: Optional[Dict[str, Any]] = None
    architecture: Optional[Dict[str, Any]] = None


@dataclass
class PhaseResult:
    """Result of a pipeline phase execution."""
    phase: PhaseType
    status: str  # "pending", "running", "completed", "failed", "awaiting_approval"
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    execution_time_ms: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class PipelineRun:
    """A single run of the generation pipeline."""
    id: Optional[int] = None
    project_id: int = 0
    author_id: str = ""
    status: str = "idle"  # idle, running, paused, awaiting_approval, completed, failed
    current_phase: Optional[PhaseType] = None
    current_chapter: int = 0
    phases: List[PhaseResult] = field(default_factory=list)
    auto_approve: bool = False

    # Cost tracking
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    estimated_cost_usd: float = 0.0

    # Timestamps
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @property
    def progress_percent(self) -> float:
        """Calculate overall progress."""
        total_phases = len(PhaseType)
        completed = sum(1 for p in self.phases if p.status == "completed")
        return (completed / total_phases) * 100


@dataclass
class StoryBibleEntry:
    """An entry in the story bible."""
    category: str  # "character", "location", "event", "item", "rule"
    name: str
    description: str
    first_appearance: int  # Chapter number
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StoryBible:
    """Living document tracking story consistency."""
    project_id: int
    entries: List[StoryBibleEntry] = field(default_factory=list)
    timeline: List[Dict[str, Any]] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.utcnow)

    def add_entry(self, entry: StoryBibleEntry) -> None:
        """Add or update an entry."""
        # Check if entry exists
        for i, existing in enumerate(self.entries):
            if existing.category == entry.category and existing.name == entry.name:
                self.entries[i] = entry
                return
        self.entries.append(entry)

    def get_entries_by_category(self, category: str) -> List[StoryBibleEntry]:
        """Get all entries of a category."""
        return [e for e in self.entries if e.category == category]

    def to_context_string(self) -> str:
        """Generate context string for prompts."""
        parts = ["# Story Bible\n"]
        for category in ["character", "location", "event", "item", "rule"]:
            entries = self.get_entries_by_category(category)
            if entries:
                parts.append(f"\n## {category.title()}s")
                for entry in entries:
                    parts.append(f"- **{entry.name}**: {entry.description}")
        return "\n".join(parts)
