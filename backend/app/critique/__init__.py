"""Critique system for evaluating generated prose."""

from .rubric import CritiqueRubric
from .evaluator import AutomaticEvaluator

__all__ = ["CritiqueRubric", "AutomaticEvaluator"]
