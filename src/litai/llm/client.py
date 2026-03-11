"""Gemini API client wrapper."""

from typing import Optional

from google import genai
from google.genai import types

from .costs import CostTracker


class LLMClient:
    """Wrapper for Gemini API."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
        project_name: Optional[str] = None,
    ):
        self.model_name = model
        self.project_name = project_name
        self.cost_tracker = CostTracker(project_name)

        self.client = genai.Client(api_key=api_key)

    def generate(
        self,
        prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.8,
    ) -> str:
        """Generate text from a prompt."""
        config = types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
        )

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config,
        )

        # Track usage
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            self.cost_tracker.track(
                input_tokens=response.usage_metadata.prompt_token_count or 0,
                output_tokens=response.usage_metadata.candidates_token_count or 0,
                model=self.model_name,
            )

        return response.text

    def get_costs(self) -> dict:
        """Get current cost tracking data."""
        return self.cost_tracker.get_summary()
