"""Automatic prose evaluator."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import re


@dataclass
class EvaluationResult:
    """Result of prose evaluation."""
    scores: Dict[str, float]
    overall_score: float
    passes: bool
    issues: List[str]
    suggestions: List[str]


class AutomaticEvaluator:
    """
    Automatic evaluator for quick prose checks.

    Provides heuristic evaluation without LLM calls for basic checks.
    Used alongside the full LLM-based critic.
    """

    def __init__(self, rubric: Any):  # CritiqueRubric
        self.rubric = rubric

    def evaluate(
        self,
        prose: str,
        blueprint: Optional[dict] = None
    ) -> EvaluationResult:
        """
        Perform automatic evaluation.

        Args:
            prose: The prose to evaluate
            blueprint: Optional blueprint for adherence checking

        Returns:
            EvaluationResult with scores and issues
        """
        scores = {}
        issues = []
        suggestions = []

        # Voice check (basic heuristics)
        voice_score, voice_issues = self._check_voice(prose)
        scores["voice"] = voice_score
        issues.extend(voice_issues)

        # Structure check
        structure_score, structure_issues = self._check_structure(prose, blueprint)
        scores["structure"] = structure_score
        issues.extend(structure_issues)

        # Language quality check
        language_score, language_issues = self._check_language(prose)
        scores["language"] = language_score
        issues.extend(language_issues)

        # Theme is harder to check automatically, give neutral score
        scores["theme"] = 7.0

        overall = self.rubric.calculate_weighted_score(scores)
        passes = overall >= self.rubric.passing_threshold

        # Generate suggestions based on issues
        if issues:
            suggestions = self._generate_suggestions(issues)

        return EvaluationResult(
            scores=scores,
            overall_score=overall,
            passes=passes,
            issues=issues,
            suggestions=suggestions
        )

    def _check_voice(self, prose: str) -> tuple[float, list[str]]:
        """Check voice authenticity (basic heuristics)."""
        score = 8.0  # Start optimistic
        issues = []

        voice_criterion = self.rubric.criteria.get("voice")
        if not voice_criterion:
            return score, issues

        prose_lower = prose.lower()

        # Check for red flags
        for flag in voice_criterion.red_flags:
            flag_lower = flag.lower()
            # Simple keyword matching
            keywords = flag_lower.split()[:3]  # First 3 words as keywords
            for kw in keywords:
                if len(kw) > 4 and kw in prose_lower:
                    score -= 0.5
                    issues.append(f"Red flag detected: {flag}")
                    break

        # Bonus for positive markers
        for marker in voice_criterion.markers:
            marker_lower = marker.lower()
            keywords = marker_lower.split()[:3]
            for kw in keywords:
                if len(kw) > 4 and kw in prose_lower:
                    score += 0.2
                    break

        return max(1.0, min(10.0, score)), issues

    def _check_structure(
        self,
        prose: str,
        blueprint: Optional[dict]
    ) -> tuple[float, list[str]]:
        """Check structural quality."""
        score = 7.5
        issues = []

        # Basic structural checks
        paragraphs = prose.split('\n\n')

        # Check paragraph count
        if len(paragraphs) < 5:
            score -= 1.0
            issues.append("Very few paragraphs - may need more structure")

        # Check for dialogue presence if blueprint suggests it
        if blueprint:
            scenes = blueprint.get("scenes", [])
            has_dialogue_notes = any(
                s.get("dialogue_notes") for s in scenes
            )
            if has_dialogue_notes:
                dialogue_count = prose.count('"')
                if dialogue_count < 4:
                    score -= 1.0
                    issues.append("Blueprint suggests dialogue but few quotes found")

        # Check paragraph length variance (good prose has variety)
        para_lengths = [len(p.split()) for p in paragraphs if p.strip()]
        if para_lengths:
            avg_len = sum(para_lengths) / len(para_lengths)
            variance = sum((l - avg_len) ** 2 for l in para_lengths) / len(para_lengths)
            if variance < 100:  # Too uniform
                score -= 0.5
                issues.append("Paragraph lengths are very uniform - consider more variety")

        return max(1.0, min(10.0, score)), issues

    def _check_language(self, prose: str) -> tuple[float, list[str]]:
        """Check language quality."""
        score = 8.0
        issues = []

        words = prose.split()
        word_count = len(words)

        # Check word count
        if word_count < 1000:
            issues.append(f"Short prose: only {word_count} words")
            score -= 1.0

        # Check for repetition (same word appearing too often)
        word_freq = {}
        for word in words:
            word_lower = word.lower().strip('.,!?"\'')
            if len(word_lower) > 5:  # Only check longer words
                word_freq[word_lower] = word_freq.get(word_lower, 0) + 1

        # Find overused words
        threshold = max(5, word_count / 100)  # More than 1% occurrence
        overused = [w for w, c in word_freq.items() if c > threshold]
        if overused:
            score -= 0.3 * len(overused[:3])  # Cap at 3
            issues.append(f"Potentially overused words: {', '.join(overused[:5])}")

        # Check sentence length variety
        sentences = re.split(r'[.!?]+', prose)
        sentence_lengths = [len(s.split()) for s in sentences if s.strip()]

        if sentence_lengths:
            avg_sent = sum(sentence_lengths) / len(sentence_lengths)

            if avg_sent > 35:
                score -= 0.5
                issues.append("Very long average sentence length")
            elif avg_sent < 8:
                score -= 0.5
                issues.append("Very short average sentence length")

            # Check variance
            variance = sum((l - avg_sent) ** 2 for l in sentence_lengths) / len(sentence_lengths)
            if variance < 20:
                score -= 0.5
                issues.append("Sentence lengths are too uniform")

        return max(1.0, min(10.0, score)), issues

    def _generate_suggestions(self, issues: list[str]) -> list[str]:
        """Generate suggestions based on issues."""
        suggestions = []

        for issue in issues:
            if "uniform" in issue.lower():
                suggestions.append("Vary your sentence and paragraph lengths for better rhythm")
            if "overused" in issue.lower():
                suggestions.append("Use synonyms or restructure to reduce word repetition")
            if "dialogue" in issue.lower():
                suggestions.append("Add dialogue as indicated in the blueprint")
            if "short prose" in issue.lower():
                suggestions.append("Expand scenes with more sensory detail and interiority")

        return list(set(suggestions))  # Remove duplicates
