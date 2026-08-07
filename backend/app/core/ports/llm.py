"""LLM Port - interface for language model interactions."""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class LLMResponse:
    """Response from LLM."""
    content: str
    input_tokens: int
    output_tokens: int
    model: str
    stop_reason: Optional[str] = None

    @property
    def text(self) -> str:
        """Alias for content — used by agent layer."""
        return self.content


class LLMPort(ABC):
    """Abstract interface for LLM operations."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        model: Optional[str] = None,
    ) -> LLMResponse:
        """
        Generate a completion from the LLM.

        Args:
            prompt: The user prompt
            system: Optional system prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            model: Model to use (implementation-specific)

        Returns:
            LLMResponse with content and metadata
        """
        pass

    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        model: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """
        Stream a completion from the LLM.

        Args:
            prompt: The user prompt
            system: Optional system prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            model: Model to use

        Yields:
            Text chunks as they're generated
        """
        pass

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate structured output matching a schema.

        Args:
            prompt: The user prompt
            schema: JSON schema for expected output
            system: Optional system prompt
            model: Model to use

        Returns:
            Parsed structured output
        """
        pass
