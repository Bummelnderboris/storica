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

import asyncio

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


# Which tier does which job — the run's cost profile, in one readable place.
#
# The rule is about the *kind* of work, not its importance. Opus goes where the output is invention
# that nothing downstream can supply: the premise, the prose itself, and adjudication, where a wrong
# ruling is permanent. Sonnet goes where the work is structured transformation against material
# already in hand — planning, extraction, and judging a unit against a slice — which is most of the
# calls. Selection is Sonnet because choosing between drafts is cheaper than writing one.
#
# Every stage still takes a `model=` argument, so this is the default, not a constraint.
STAGE_MODELS: Dict[str, str] = {
    # invention
    "conception": "opus",
    "prose": "opus",
    "adjudicator": "opus",
    "final_auditor": "opus",
    # structured transformation
    "world_cast": "sonnet",
    "macro_arc": "sonnet",
    "chapter_spec": "sonnet",
    "reconcile": "sonnet",
    "selection": "sonnet",
    # judgement against a slice
    "canon_consistency": "sonnet",
    "intent": "sonnet",
    "micro_sense": "sonnet",
    "voice": "sonnet",
    "vitality": "sonnet",
    "repair_verifier": "sonnet",
}


def stage_model(stage: str) -> str:
    """The default alias for one stage or checker. Unknown names fall back to sonnet."""
    return STAGE_MODELS.get(stage, "sonnet")


async def gather_draws(coros):
    """
    Run k independent draws and surface the first failure only after all of them have finished.

    `asyncio.gather` with its default would propagate the first exception while the siblings are
    still in flight, leaving their results unretrieved. That matters for more than tidiness: under
    the replay driver every unanswered draw writes a request file, so letting all k complete means
    one stop produces all k requests to answer, instead of one stop per draw.
    """
    results = await asyncio.gather(*coros, return_exceptions=True)
    for r in results:
        if isinstance(r, BaseException):
            raise r
    return results


# Published per-million-token prices (anthropic.com/pricing, checked 2026-09-01), used only to turn
# a token count into a number a human can act on. Wrong prices produce a wrong estimate and nothing
# else — no behaviour depends on this — but check them against the current price list before quoting
# a figure, because they go stale silently and a stale rate is worse than no rate.
PRICES: Dict[str, tuple[float, float]] = {   # alias -> (input $/Mtok, output $/Mtok)
    "opus": (5.00, 25.00),
    "sonnet": (2.00, 10.00),
    "haiku": (1.00, 5.00),
}


@dataclass
class Usage:
    """
    What a run actually cost, accumulated across every call.

    The pipeline has always been able to say what it *did*; it could not say what that came to.
    That is the one number a person needs before letting it write a second book, so it is counted
    here — at the only place every call passes through — rather than reconstructed from the trace.
    """

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    by_model: Dict[str, int] = field(default_factory=dict)   # alias -> calls
    cost_usd: float = 0.0

    def record(self, *, model: str, input_tokens: int, output_tokens: int) -> None:
        self.calls += 1
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.by_model[model] = self.by_model.get(model, 0) + 1
        rate_in, rate_out = PRICES.get(model, (0.0, 0.0))
        self.cost_usd += (input_tokens * rate_in + output_tokens * rate_out) / 1_000_000

    def as_dict(self) -> Dict[str, Any]:
        return {
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "calls_by_model": dict(sorted(self.by_model.items())),
            "estimated_cost_usd": round(self.cost_usd, 4),
        }

    def summary(self) -> str:
        return (
            f"{self.calls} calls, {self.input_tokens:,} in / {self.output_tokens:,} out tokens, "
            f"~${self.cost_usd:,.2f}"
        )


class LLMRefusal(RuntimeError):
    """The model declined the request (`stop_reason == "refusal"`)."""


class StructuredLLM(ABC):
    """
    Port: the two things the pipeline ever asks of a model.

    `parse` is how every *plan* and *judgement* is produced — schema-constrained, so nothing
    downstream has to re-interpret prose to find out what was decided. `generate` exists only for
    the one artifact that genuinely is prose (stage 5), and even that is generated *from* canon
    and reconciled back *into* it, never read back as truth.

    Both take a `draw` index. The pipeline deliberately makes the *same* call more than once in two
    places — k prose candidates, and k consensus samples of one checker — and those draws must stay
    distinguishable. A live model ignores `draw` (sampling already differs); `ReplayLLM` uses it to
    give each draw its own cache slot. Passing it explicitly rather than counting calls internally
    is what makes those fan-outs safe to run concurrently.

    Every adapter carries a `usage` counter so a caller can ask what a run cost without knowing
    which adapter it got.
    """

    @property
    def usage(self) -> "Usage":
        """The run's token counter. Lazily created, so an adapter that never sets one still has one."""
        found = self.__dict__.get("_usage")
        if found is None:
            found = self.__dict__["_usage"] = Usage()
        return found

    @usage.setter
    def usage(self, value: "Usage") -> None:
        self.__dict__["_usage"] = value

    @abstractmethod
    async def parse(
        self,
        *,
        prompt: str,
        schema: Type[T],
        system: Optional[str] = None,
        model: str = "opus",
        max_tokens: int = 16000,
        draw: int = 1,
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
        draw: int = 1,
    ) -> str:
        """Generate free text. Prose only — never used to carry structure."""


class AnthropicStructuredLLM(StructuredLLM):
    """Structured outputs via the Anthropic API. The only place the SDK is touched in v2."""

    #: How many calls may be in flight at once. The candidate and consensus fan-outs each open
    #: k streams concurrently; without a bound, a modest per-minute output limit turns into a 429
    #: that escapes as a traceback instead of a wait.
    DEFAULT_CONCURRENCY = 4
    #: The SDK's own backoff on 429/5xx. Its default of 2 is too few for k parallel Opus streams.
    DEFAULT_MAX_RETRIES = 6

    def __init__(
        self,
        api_key: Optional[str] = None,
        client: Any = None,
        *,
        concurrency: int = DEFAULT_CONCURRENCY,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ):
        if client is None:
            from anthropic import AsyncAnthropic

            kwargs: Dict[str, Any] = {"max_retries": max_retries}
            if api_key:
                kwargs["api_key"] = api_key
            client = AsyncAnthropic(**kwargs)
        self.client = client
        self.usage = Usage()
        self._in_flight = asyncio.Semaphore(max(1, concurrency))

    def _finish(self, model: str, raw) -> None:
        """
        Account for one call, then check whether it was refused — in that order, for both
        `parse` and `generate`, so a refusal is billed the way the API billed it.
        """
        u = getattr(raw, "usage", None)
        self.usage.record(
            model=model,
            input_tokens=getattr(u, "input_tokens", 0) or 0,
            output_tokens=getattr(u, "output_tokens", 0) or 0,
        )
        # Check stop_reason before touching content: a refusal returns HTTP 200 with no parse.
        if getattr(raw, "stop_reason", None) == "refusal":
            raise LLMRefusal(f"model refused ({getattr(raw, 'stop_details', None)})")

    async def parse(
        self,
        *,
        prompt: str,
        schema: Type[T],
        system: Optional[str] = None,
        model: str = "opus",
        max_tokens: int = 16000,
        draw: int = 1,  # noqa: ARG002 — sampling already differs; only the replay cache needs it
    ) -> T:
        async with self._in_flight:
            response = await self.client.messages.parse(
                model=resolve_model(model),
                max_tokens=max_tokens,
                system=system or "You are part of an autonomous novel-writing pipeline.",
                messages=[{"role": "user", "content": prompt}],
                output_format=schema,
            )
        self._finish(model, response)
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
        draw: int = 1,  # noqa: ARG002 — see `parse`
    ) -> str:
        # Streamed: prose runs long, and a non-streaming request at this max_tokens risks an
        # HTTP timeout. We only want the finished text, so we never touch the events.
        async with self._in_flight:
            async with self.client.messages.stream(
                model=resolve_model(model),
                max_tokens=max_tokens,
                system=system or "You are part of an autonomous novel-writing pipeline.",
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                message = await stream.get_final_message()

        self._finish(model, message)
        return "".join(b.text for b in message.content if b.type == "text")


@dataclass
class FakeCall:
    prompt: str
    schema: str          # "<text>" for a `generate` call
    system: Optional[str]
    model: str
    draw: int = 1


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
    usage: Usage = field(default_factory=Usage)

    async def parse(
        self,
        *,
        prompt: str,
        schema: Type[T],
        system: Optional[str] = None,
        model: str = "opus",
        max_tokens: int = 16000,
        draw: int = 1,
    ) -> T:
        self.calls.append(FakeCall(prompt=prompt, schema=schema.__name__, system=system, model=model, draw=draw))
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
        draw: int = 1,
    ) -> str:
        self.calls.append(FakeCall(prompt=prompt, schema="<text>", system=system, model=model, draw=draw))
        if not self.texts:
            raise AssertionError("FakeStructuredLLM: no queued text for generate()")
        return self.texts.pop(0)
