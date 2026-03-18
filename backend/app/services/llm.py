"""Async LLM client wrapper."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

from google import genai

from app.config import get_settings

settings = get_settings()

# Model pricing per million tokens
MODEL_PRICING = {
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
}


class AsyncLLMClient:
    """Async wrapper for Gemini LLM calls."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.0-flash",
        progress_callback: Optional[Callable[[str, int], None]] = None,
    ):
        self.api_key = api_key or settings.gemini_api_key
        self.model = model
        self.progress_callback = progress_callback
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._client: Optional[genai.Client] = None

    def _get_client(self) -> genai.Client:
        """Get or create the Gemini client."""
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def _sync_generate(
        self,
        prompt: str,
        max_tokens: int = 8192,
        temperature: float = 0.8,
    ) -> tuple[str, int, int]:
        """Synchronous generation for thread pool execution."""
        client = self._get_client()
        response = client.models.generate_content(
            model=self.model,
            contents=prompt,
            config={
                "max_output_tokens": max_tokens,
                "temperature": temperature,
            },
        )

        text = response.text
        input_tokens = response.usage_metadata.prompt_token_count
        output_tokens = response.usage_metadata.candidates_token_count

        return text, input_tokens, output_tokens

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 8192,
        temperature: float = 0.8,
    ) -> tuple[str, int, int]:
        """Generate text asynchronously.

        Returns:
            Tuple of (generated_text, input_tokens, output_tokens)
        """
        loop = asyncio.get_event_loop()

        if self.progress_callback:
            self.progress_callback("Generating content...", 50)

        result = await loop.run_in_executor(
            self._executor,
            self._sync_generate,
            prompt,
            max_tokens,
            temperature,
        )

        if self.progress_callback:
            self.progress_callback("Generation complete", 100)

        return result

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate the cost of a generation."""
        pricing = MODEL_PRICING.get(
            self.model, {"input": 0.10, "output": 0.40}
        )
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    async def close(self):
        """Clean up resources."""
        self._executor.shutdown(wait=False)
