"""
Agent registry for factory pattern and agent discovery.
"""

from typing import Type, Dict, Any, Optional
from .base import BaseAgent, AgentPhase


class AgentRegistry:
    """
    Central registry for all pipeline agents.

    Provides factory methods for creating agents and
    discovering available agents for each phase.
    """

    _agents: Dict[AgentPhase, Type[BaseAgent]] = {}
    _instances: Dict[AgentPhase, BaseAgent] = {}

    @classmethod
    def register(cls, phase: AgentPhase):
        """
        Decorator to register an agent class for a phase.

        Usage:
            @AgentRegistry.register(AgentPhase.TOPIC_EXPLORATION)
            class TopicExplorerAgent(BaseAgent):
                ...
        """
        def decorator(agent_class: Type[BaseAgent]):
            cls._agents[phase] = agent_class
            return agent_class
        return decorator

    @classmethod
    def get_agent_class(cls, phase: AgentPhase) -> Optional[Type[BaseAgent]]:
        """Get the agent class for a phase."""
        return cls._agents.get(phase)

    @classmethod
    def get_agent(
        cls,
        phase: AgentPhase,
        llm_service: Any,
        prompt_engine: Any,
        cached: bool = True
    ) -> Optional[BaseAgent]:
        """
        Get an agent instance for a phase.

        Args:
            phase: The pipeline phase
            llm_service: LLM service instance
            prompt_engine: Prompt engine instance
            cached: If True, reuse existing instance

        Returns:
            Agent instance or None if not registered
        """
        if cached and phase in cls._instances:
            return cls._instances[phase]

        agent_class = cls._agents.get(phase)
        if agent_class is None:
            return None

        instance = agent_class(llm_service, prompt_engine)

        if cached:
            cls._instances[phase] = instance

        return instance

    @classmethod
    def list_phases(cls) -> list[AgentPhase]:
        """List all registered phases."""
        return list(cls._agents.keys())

    @classmethod
    def list_agents(cls) -> Dict[str, str]:
        """List all registered agents with their descriptions."""
        return {
            phase.value: agent_class.description
            for phase, agent_class in cls._agents.items()
        }

    @classmethod
    def clear_cache(cls) -> None:
        """Clear cached agent instances."""
        cls._instances.clear()

    @classmethod
    def is_registered(cls, phase: AgentPhase) -> bool:
        """Check if an agent is registered for a phase."""
        return phase in cls._agents
