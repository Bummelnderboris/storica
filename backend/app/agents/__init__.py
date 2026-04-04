"""
Multi-agent system for Storica novel generation pipeline.
"""

from .base import BaseAgent, AgentContext, AgentResult
from .registry import AgentRegistry

__all__ = [
    "BaseAgent",
    "AgentContext",
    "AgentResult",
    "AgentRegistry",
]
