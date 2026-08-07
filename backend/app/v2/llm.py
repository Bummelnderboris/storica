"""
Structured LLM access for the v2 pipeline.

Every v2 stage emits a **validated Pydantic model**, never prose to be re-parsed — this is the
single change that removes the F6/F10 cascade at the root (see /DESIGN.md §5). We therefore use
the Anthropic structured-outputs path (`messages.parse`), which constrains the response to the
schema, instead of v1's "ask for JSON, regex it out of the text" approach.

Two rules the stage schemas must obey (Anthropic structured-output limits):
- every object is `extra="forbid"` (→ `additionalProperties: false`), and
- **no `Dict[...]` fields** — a dict maps to `additionalProperties: <type>`, which is not supported.
  Stages therefore emit *lists with explicit ids/keys* and the mapping to canon dicts happens here
  in Python. `StoryModel` itself keeps its dicts; only the LLM-facing draft schemas are flattened.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

# Stage → model aliases from DESIGN §5. Aliases are resolved late so the pipeline talks about
# "opus"/"sonnet" and the current model IDs live in exactly one place.
MODELS: Dict[str, str] = {
    "opus": "claude-opus-5",
    "sonnet": "claude-sonnet-5",
    "haiku": "claude-haiku-4-5",
}


def resolve_model(model: str) -> str:
    """Map a stage alias ('opus') to a model id; pass through anything already an id."""
    return MODELS.get(model, model)


class LLMRefusal(RuntimeError):
    """The model declined the request (`stop_reason == "refusal"`)."""


class StructuredLLM(ABC):
    """
    Port: the two things the pipeline ever asks of a model.

    `parse` is how every *plan* and *judgement* is produced — schema-constrained, so nothing
    downstream has to re-interpret prose to find out what was decided. `generate` exists only for
    the one artifact that genuinely is prose (stage 5), and even that is generated *from* canon
    and reconciled back *into* it, never read back as truth.
    """

    @abstractmethod
    async def parse(
        self,
        *,
        prompt: str,
        schema: Type[T],
        system: Optional[str] = None,
        model: str = "opus",
        max_tokens: int = 16000,
    ) -> T:
        """Generate a response constrained to `schema` and return it parsed."""

    @abstractmethod
    async def generate(
        self,
        *,
        prompt: str,
        system: Optional[str] = None,
        model: str = "opus",
        max_tokens: int = 32000,
    ) -> str:
        """Generate free text. Prose only — never used to carry structure."""


class AnthropicStructuredLLM(StructuredLLM):
    """Structured outputs via the Anthropic API. The only place the SDK is touched in v2."""

    def __init__(self, api_key: Optional[str] = None, client: Any = None):
        if client is None:
            from anthropic import AsyncAnthropic

            client = AsyncAnthropic(api_key=api_key) if api_key else AsyncAnthropic()
        self.client = client

    async def parse(
        self,
        *,
        prompt: str,
        schema: Type[T],
        system: Optional[str] = None,
        model: str = "opus",
        max_tokens: int = 16000,
    ) -> T:
        response = await self.client.messages.parse(
            model=resolve_model(model),
            max_tokens=max_tokens,
            system=system or "You are part of an autonomous novel-writing pipeline.",
            messages=[{"role": "user", "content": prompt}],
            output_format=schema,
        )
        # Check stop_reason before touching content: a refusal returns HTTP 200 with no parse.
        if response.stop_reason == "refusal":
            raise LLMRefusal(f"model refused ({getattr(response, 'stop_details', None)})")
        parsed = response.parsed_output
        if parsed is None:
            raise RuntimeError(
                f"no parsed output (stop_reason={response.stop_reason}); "
                f"raise max_tokens if this is truncation"
            )
        return parsed

    async def generate(
        self,
        *,
        prompt: str,
        system: Optional[str] = None,
        model: str = "opus",
        max_tokens: int = 32000,
    ) -> str:
        # Streamed: prose runs long, and a non-streaming request at this max_tokens risks an
        # HTTP timeout. We only want the finished text, so we never touch the events.
        async with self.client.messages.stream(
            model=resolve_model(model),
            max_tokens=max_tokens,
            system=system or "You are part of an autonomous novel-writing pipeline.",
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            message = await stream.get_final_message()

        if message.stop_reason == "refusal":
            raise LLMRefusal(f"model refused ({getattr(message, 'stop_details', None)})")
        return "".join(b.text for b in message.content if b.type == "text")


@dataclass
class FakeCall:
    prompt: str
    schema: str          # "<text>" for a `generate` call
    system: Optional[str]
    model: str


@dataclass
class FakeStructuredLLM(StructuredLLM):
    """
    Test double. Hand it a queue of already-built Pydantic instances; each `parse` pops the next
    one whose type matches the requested schema, so queue order does not have to match call order.
    `texts` is the separate FIFO queue backing `generate`. Records every call for assertions.
    """

    responses: List[BaseModel] = field(default_factory=list)
    texts: List[str] = field(default_factory=list)
    calls: List[FakeCall] = field(default_factory=list)

    async def parse(
        self,
        *,
        prompt: str,
        schema: Type[T],
        system: Optional[str] = None,
        model: str = "opus",
        max_tokens: int = 16000,
    ) -> T:
        self.calls.append(FakeCall(prompt=prompt, schema=schema.__name__, system=system, model=model))
        for i, r in enumerate(self.responses):
            if isinstance(r, schema):
                return self.responses.pop(i)  # type: ignore[return-value]
        raise AssertionError(
            f"FakeStructuredLLM: no queued response of type {schema.__name__} "
            f"(queued: {[type(r).__name__ for r in self.responses]})"
        )

    async def generate(
        self,
        *,
        prompt: str,
        system: Optional[str] = None,
        model: str = "opus",
        max_tokens: int = 32000,
    ) -> str:
        self.calls.append(FakeCall(prompt=prompt, schema="<text>", system=system, model=model))
        if not self.texts:
            raise AssertionError("FakeStructuredLLM: no queued text for generate()")
        return self.texts.pop(0)
