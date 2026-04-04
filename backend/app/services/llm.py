"""LLM Service for Anthropic Claude API."""

import os
from dataclasses import dataclass
from typing import AsyncIterator, Optional

from anthropic import AsyncAnthropic


@dataclass
class LLMResponse:
    """Response from LLM generation."""
    text: str
    input_tokens: int
    output_tokens: int
    model: str
    stop_reason: Optional[str] = None


@dataclass
class LLMChunk:
    """A chunk from streaming response."""
    text: str
    is_final: bool = False


class LLMService:
    """
    LLM Service using Anthropic Claude API.

    Provides both synchronous and streaming generation.
    """

    # Model mappings
    MODELS = {
        "sonnet": "claude-sonnet-4-20250514",
        "opus": "claude-opus-4-20250514",
        "haiku": "claude-3-5-haiku-20241022",
        "default": "claude-sonnet-4-20250514"
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: str = "sonnet"
    ):
        """
        Initialize LLM service.

        Args:
            api_key: Anthropic API key (or from env)
            default_model: Default model to use
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        self.client = AsyncAnthropic(api_key=self.api_key)
        self.default_model = self.MODELS.get(default_model, self.MODELS["default"])

    def _resolve_model(self, model: Optional[str]) -> str:
        """Resolve model name to model ID."""
        if model is None:
            return self.default_model
        return self.MODELS.get(model, model)

    async def generate(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        model: Optional[str] = None
    ) -> LLMResponse:
        """
        Generate a response from the LLM.

        Args:
            prompt: User prompt
            system: System prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            model: Model to use (sonnet, opus, haiku, or full ID)

        Returns:
            LLMResponse with generated text and token counts
        """
        model_id = self._resolve_model(model)

        messages = [{"role": "user", "content": prompt}]

        response = await self.client.messages.create(
            model=model_id,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system if system else None,
            messages=messages
        )

        text = ""
        for block in response.content:
            if block.type == "text":
                text += block.text

        return LLMResponse(
            text=text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=model_id,
            stop_reason=response.stop_reason
        )

    async def generate_stream(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        model: Optional[str] = None
    ) -> AsyncIterator[LLMChunk]:
        """
        Generate a streaming response from the LLM.

        Args:
            prompt: User prompt
            system: System prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            model: Model to use

        Yields:
            LLMChunk for each text chunk
        """
        model_id = self._resolve_model(model)

        messages = [{"role": "user", "content": prompt}]

        async with self.client.messages.stream(
            model=model_id,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system if system else None,
            messages=messages
        ) as stream:
            async for text in stream.text_stream:
                yield LLMChunk(text=text, is_final=False)

            yield LLMChunk(text="", is_final=True)

    async def generate_with_extended_thinking(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 8192,
        thinking_budget: int = 4096,
        model: str = "opus"
    ) -> LLMResponse:
        """
        Generate with extended thinking (Claude's chain-of-thought).

        Uses Claude's extended thinking capability for complex reasoning.

        Args:
            prompt: User prompt
            system: System prompt
            max_tokens: Maximum tokens for response
            thinking_budget: Token budget for thinking
            model: Model to use (recommend opus for best thinking)

        Returns:
            LLMResponse with final output
        """
        model_id = self._resolve_model(model)

        messages = [{"role": "user", "content": prompt}]

        # Extended thinking prompt wrapper
        thinking_system = f"""{system}

Before responding, think through this step by step. Consider multiple approaches,
potential issues, and the best way to achieve the goal. Then provide your final response."""

        response = await self.client.messages.create(
            model=model_id,
            max_tokens=max_tokens + thinking_budget,
            temperature=0.7,
            system=thinking_system,
            messages=messages
        )

        text = ""
        for block in response.content:
            if block.type == "text":
                text += block.text

        return LLMResponse(
            text=text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=model_id,
            stop_reason=response.stop_reason
        )

    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model: Optional[str] = None
    ) -> float:
        """
        Estimate cost for token usage.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model: Model used

        Returns:
            Estimated cost in USD
        """
        model_id = self._resolve_model(model)

        # Pricing per 1K tokens (as of 2025)
        pricing = {
            "claude-sonnet-4-20250514": {"input": 0.003, "output": 0.015},
            "claude-opus-4-20250514": {"input": 0.015, "output": 0.075},
            "claude-3-5-haiku-20241022": {"input": 0.0008, "output": 0.004}
        }

        rates = pricing.get(model_id, pricing["claude-sonnet-4-20250514"])

        input_cost = (input_tokens / 1000) * rates["input"]
        output_cost = (output_tokens / 1000) * rates["output"]

        return round(input_cost + output_cost, 6)


# Singleton instance
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Get or create the LLM service singleton."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
