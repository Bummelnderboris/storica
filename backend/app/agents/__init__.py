"""
Multi-agent system for Storica novel generation pipeline.
"""

from .base import BaseAgent, AgentContext, AgentResult, AgentPhase
from .registry import AgentRegistry

# Import phase modules to trigger @AgentRegistry.register() decorators.
# Phase 0 (author loading) is handled directly by the orchestrator.
from .phase1_topic import explorer as _phase1  # noqa: F401
from .phase2_thesis import developer as _phase2  # noqa: F401
from .phase3_character import deriver as _phase3  # noqa: F401
from .phase4_architecture import architect as _phase4  # noqa: F401
from .phase5_blueprint import planner as _phase5  # noqa: F401
# Phase 6 agents are instantiated directly by ProseGenerationLoop
from .phase7_consistency import guardian as _phase7  # noqa: F401

__all__ = [
    "BaseAgent",
    "AgentContext",
    "AgentPhase",
    "AgentResult",
    "AgentRegistry",
]
