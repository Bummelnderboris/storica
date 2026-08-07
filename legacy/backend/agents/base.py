"""
Base classes for the multi-agent pipeline system.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Generic, Optional, TypeVar
from pydantic import BaseModel


class AgentPhase(str, Enum):
    """Pipeline phases."""
    AUTHOR_LOADING = "phase0_author"
    TOPIC_EXPLORATION = "phase1_topic"
    THESIS_DEVELOPMENT = "phase2_thesis"
    CHARACTER_DERIVATION = "phase3_character"
    STORY_ARCHITECTURE = "phase4_architecture"
    CHAPTER_BLUEPRINTS = "phase5_blueprint"
    PROSE_GENERATION = "phase6_prose"
    CONSISTENCY_CHECK = "phase7_consistency"


class AgentStatus(str, Enum):
    """Agent execution status."""
    PENDING = "pending"
    REASONING = "reasoning"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    AWAITING_APPROVAL = "awaiting_approval"


@dataclass
class AgentContext:
    """
    Context passed to agents during execution.
    Contains all necessary data for the agent to perform its task.
    """
    project_id: int
    author_id: str
    author_profile: dict = field(default_factory=dict)
    story_dna: dict = field(default_factory=dict)
    previous_outputs: dict = field(default_factory=dict)
    story_bible: dict = field(default_factory=dict)
    chapter_index: Optional[int] = None
    iteration: int = 0
    max_iterations: int = 3

    # Cost tracking
    input_tokens: int = 0
    output_tokens: int = 0

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)

    def add_token_usage(self, input_tokens: int, output_tokens: int) -> None:
        """Track token usage."""
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens


InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


@dataclass
class AgentResult(Generic[OutputT]):
    """
    Result returned by an agent after execution.
    """
    success: bool
    output: Optional[OutputT] = None
    reasoning: Optional[str] = None
    error: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    execution_time_ms: int = 0
    requires_approval: bool = False

    @classmethod
    def success_result(
        cls,
        output: OutputT,
        reasoning: Optional[str] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        execution_time_ms: int = 0,
        requires_approval: bool = False
    ) -> "AgentResult[OutputT]":
        """Create a successful result."""
        return cls(
            success=True,
            output=output,
            reasoning=reasoning,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            execution_time_ms=execution_time_ms,
            requires_approval=requires_approval
        )

    @classmethod
    def failure_result(
        cls,
        error: str,
        reasoning: Optional[str] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        execution_time_ms: int = 0
    ) -> "AgentResult[OutputT]":
        """Create a failure result."""
        return cls(
            success=False,
            error=error,
            reasoning=reasoning,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            execution_time_ms=execution_time_ms
        )


class BaseAgent(ABC, Generic[InputT, OutputT]):
    """
    Abstract base class for all pipeline agents.

    Each agent is responsible for a specific phase of the generation pipeline.
    Agents can reason about their task before execution and produce structured output.
    """

    phase: AgentPhase
    name: str
    description: str
    requires_approval: bool = False

    def __init__(self, llm_service: Any, prompt_engine: Any):
        """
        Initialize the agent.

        Args:
            llm_service: Service for LLM API calls
            prompt_engine: Engine for loading prompt templates
        """
        self.llm = llm_service
        self.prompts = prompt_engine

    @abstractmethod
    async def execute(
        self,
        input_data: InputT,
        context: AgentContext
    ) -> AgentResult[OutputT]:
        """
        Execute the agent's main task.

        Args:
            input_data: Input data specific to this agent
            context: Shared context for the pipeline

        Returns:
            AgentResult containing the output or error
        """
        pass

    async def reason(
        self,
        input_data: InputT,
        context: AgentContext
    ) -> str:
        """
        Pre-execution reasoning phase.

        Allows the agent to think through its approach before generating output.
        Can be overridden by subclasses for custom reasoning.

        Args:
            input_data: Input data specific to this agent
            context: Shared context for the pipeline

        Returns:
            Reasoning text explaining the agent's approach
        """
        prompt = self._build_reasoning_prompt(input_data, context)
        response = await self.llm.generate(
            prompt=prompt,
            system=f"You are the {self.name} agent. Think through your approach step by step.",
            max_tokens=1000
        )
        context.add_token_usage(response.input_tokens, response.output_tokens)
        return response.text

    def _build_reasoning_prompt(
        self,
        input_data: InputT,
        context: AgentContext
    ) -> str:
        """Build the reasoning prompt. Override for custom behavior."""
        return f"""
Task: {self.description}

Input: {input_data.model_dump_json(indent=2)}

Author Profile: {context.author_profile.get('name', 'Unknown')}

Think through your approach for this task. What are the key considerations?
What should you focus on? What potential issues should you watch for?
"""

    def validate_input(self, input_data: InputT) -> tuple[bool, Optional[str]]:
        """
        Validate input data before execution.

        Returns:
            Tuple of (is_valid, error_message)
        """
        return True, None

    def validate_output(self, output: OutputT) -> tuple[bool, Optional[str]]:
        """
        Validate output data after execution.

        Returns:
            Tuple of (is_valid, error_message)
        """
        return True, None


class StreamingAgent(BaseAgent[InputT, OutputT]):
    """
    Base class for agents that support streaming output.
    Used for prose generation where real-time feedback is valuable.
    """

    @abstractmethod
    async def execute_streaming(
        self,
        input_data: InputT,
        context: AgentContext,
        on_chunk: callable
    ) -> AgentResult[OutputT]:
        """
        Execute with streaming output.

        Args:
            input_data: Input data specific to this agent
            context: Shared context for the pipeline
            on_chunk: Callback for each output chunk

        Returns:
            AgentResult containing the complete output
        """
        pass
