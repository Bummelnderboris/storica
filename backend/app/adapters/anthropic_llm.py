"""Anthropic LLM Adapter - implements LLMPort using Anthropic API."""

import json
from typing import AsyncIterator, Optional, Dict, Any

from anthropic import AsyncAnthropic

from ..core.ports.llm import LLMPort, LLMResponse


class AnthropicLLMAdapter(LLMPort):
    """
    LLM adapter using Anthropic's Claude API.

    This is the only place where Anthropic SDK is used.
    """

    MODELS = {
        "sonnet": "claude-sonnet-4-20250514",
        "opus": "claude-opus-4-20250514",
        "haiku": "claude-3-5-haiku-20241022",
    }

    def __init__(self, api_key: str, default_model: str = "sonnet"):
        """
        Initialize with API key.

        Args:
            api_key: Anthropic API key
            default_model: Default model to use ("sonnet", "opus", "haiku")
        """
        self.client = AsyncAnthropic(api_key=api_key)
        self.default_model = self.MODELS.get(default_model, default_model)

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        model: Optional[str] = None,
    ) -> LLMResponse:
        """Generate a completion."""
        model_id = self._resolve_model(model)

        message = await self.client.messages.create(
            model=model_id,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system or "You are a helpful assistant.",
            messages=[{"role": "user", "content": prompt}],
        )

        return LLMResponse(
            content=message.content[0].text,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
            model=model_id,
            stop_reason=message.stop_reason,
        )

    async def generate_stream(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        model: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """Stream a completion."""
        model_id = self._resolve_model(model)

        async with self.client.messages.stream(
            model=model_id,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system or "You are a helpful assistant.",
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate structured output."""
        # Add schema instructions to prompt
        structured_prompt = f"""{prompt}

Respond with valid JSON matching this schema:
{json.dumps(schema, indent=2)}

Return ONLY the JSON object, no other text."""

        response = await self.generate(
            prompt=structured_prompt,
            system=system,
            model=model,
            temperature=0.3,  # Lower temp for structured output
        )

        # Parse JSON from response
        import re
        json_match = re.search(r'\{[\s\S]*\}', response.content)
        if json_match:
            return json.loads(json_match.group())

        raise ValueError(f"Could not parse JSON from response: {response.content[:200]}")

    def _resolve_model(self, model: Optional[str]) -> str:
        """Resolve model name to model ID."""
        if model is None:
            return self.default_model
        return self.MODELS.get(model, model)
