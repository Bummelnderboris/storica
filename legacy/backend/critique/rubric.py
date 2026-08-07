"""Critique rubric management."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class CriterionWeight:
    """A weighted evaluation criterion."""
    name: str
    weight: float
    description: str
    markers: List[str] = field(default_factory=list)
    red_flags: List[str] = field(default_factory=list)


@dataclass
class CritiqueRubric:
    """
    Rubric for evaluating prose against author style.

    Contains weighted criteria for voice, theme, structure, and language.
    """

    author_id: str
    author_name: str
    criteria: Dict[str, CriterionWeight] = field(default_factory=dict)
    passing_threshold: float = 7.0

    @classmethod
    def from_author_profile(cls, author_id: str, profile_data: dict) -> "CritiqueRubric":
        """Create rubric from author profile data."""
        rubric_data = profile_data.get("critique_rubric", {})
        metadata = profile_data.get("metadata", {})

        rubric = cls(
            author_id=author_id,
            author_name=metadata.get("name", author_id)
        )

        # Voice criterion
        rubric.criteria["voice"] = CriterionWeight(
            name="Voice Authenticity",
            weight=rubric_data.get("weight_voice", 0.35),
            description="How well the prose captures the author's distinctive voice",
            markers=rubric_data.get("voice_markers", []),
            red_flags=rubric_data.get("red_flags", [])
        )

        # Theme criterion
        rubric.criteria["theme"] = CriterionWeight(
            name="Thematic Alignment",
            weight=rubric_data.get("weight_theme", 0.25),
            description="How well themes manifest in the prose",
            markers=rubric_data.get("thematic_alignment", [])
        )

        # Structure criterion
        rubric.criteria["structure"] = CriterionWeight(
            name="Structural Quality",
            weight=rubric_data.get("weight_structure", 0.20),
            description="How well the prose follows the blueprint structure"
        )

        # Language criterion
        rubric.criteria["language"] = CriterionWeight(
            name="Language Quality",
            weight=rubric_data.get("weight_language", 0.20),
            description="Overall prose quality, clarity, and flow"
        )

        return rubric

    def to_prompt_format(self) -> str:
        """Format rubric for use in prompts."""
        parts = [f"# Critique Rubric for {self.author_name}\n"]

        for key, criterion in self.criteria.items():
            parts.append(f"## {criterion.name} (Weight: {criterion.weight:.0%})")
            parts.append(f"{criterion.description}\n")

            if criterion.markers:
                parts.append("**Positive Markers:**")
                for marker in criterion.markers[:5]:
                    parts.append(f"- {marker}")
                parts.append("")

            if criterion.red_flags:
                parts.append("**Red Flags:**")
                for flag in criterion.red_flags[:5]:
                    parts.append(f"- {flag}")
                parts.append("")

        parts.append(f"\n**Passing Threshold:** {self.passing_threshold}/10")

        return "\n".join(parts)

    def calculate_weighted_score(self, scores: Dict[str, float]) -> float:
        """
        Calculate weighted overall score from individual scores.

        Args:
            scores: Dict mapping criterion key to score (1-10)

        Returns:
            Weighted average score
        """
        total_weight = 0
        weighted_sum = 0

        for key, criterion in self.criteria.items():
            if key in scores:
                weighted_sum += scores[key] * criterion.weight
                total_weight += criterion.weight

        if total_weight == 0:
            return 5.0  # Default middle score

        return weighted_sum / total_weight

    def passes(self, scores: Dict[str, float]) -> bool:
        """Check if scores pass the threshold."""
        return self.calculate_weighted_score(scores) >= self.passing_threshold
