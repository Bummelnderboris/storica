"""
Prove the Anthropic adapter works, for about a tenth of a cent.

`AnthropicStructuredLLM` is the only module in this repository that has never executed. Every test
in the suite runs against `FakeStructuredLLM` or `ReplayLLM`, which is what makes them fast and
free — and also means the live path is the one thing they cannot vouch for. A whole book is an
expensive way to discover that `messages.parse` moved.

So this exercises all three live paths on the cheapest model, with tiny prompts:

  1. `parse`     — schema-constrained output. 15 of the 16 agent roles use this.
  2. `generate`  — the streamed prose path. One role uses it.
  3. `usage`     — that token accounting is actually populated from the response.

Run it before the first real run, and after any SDK upgrade:

    .venv/bin/python tools/smoke_test_api.py

Needs `ANTHROPIC_API_KEY` in the environment or in `.env` at the repo root.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from storica.llm import AnthropicStructuredLLM, LLMRefusal  # noqa: E402

MODEL = "haiku"  # the cheapest tier; this is a wiring check, not a capability check


class Probe(BaseModel):
    """Deliberately trivial: if this comes back as a validated instance, the schema path works."""

    model_config = ConfigDict(extra="forbid")

    colour: str = Field(description="One colour named in the prompt.")
    count: int = Field(description="How many colours the prompt named.")


def _load_dotenv() -> None:
    path = REPO_ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip("'\"")
        if value:  # an empty assignment in .env is not a credential
            os.environ.setdefault(key.strip(), value)


async def main() -> int:
    _load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "ANTHROPIC_API_KEY is not set (and .env does not supply one).\n"
            "Export it, or put it in .env — see .env.example."
        )
        return 1

    llm = AnthropicStructuredLLM()

    print(f"1/3  parse()     — schema-constrained, model={MODEL}")
    try:
        probe = await llm.parse(
            prompt="The colours are red and blue. Name one of them and say how many there are.",
            schema=Probe,
            system="Answer only from the prompt.",
            model=MODEL,
            max_tokens=200,
        )
    except LLMRefusal as refusal:
        print(f"     refused: {refusal}")
        return 1
    assert isinstance(probe, Probe), f"expected a Probe, got {type(probe).__name__}"
    print(f"     ok — {probe!r}")

    print(f"2/3  generate()  — streamed free text, model={MODEL}")
    text = await llm.generate(
        prompt="Write exactly one short sentence about a locked door.",
        system="Write prose and nothing else.",
        model=MODEL,
        max_tokens=100,
    )
    assert text.strip(), "streaming returned no text"
    print(f"     ok — {text.strip()[:70]!r}")

    print("3/3  usage       — token accounting populated from the live response")
    assert llm.usage.calls == 2, f"expected 2 calls, counted {llm.usage.calls}"
    assert llm.usage.input_tokens > 0 and llm.usage.output_tokens > 0, "no tokens counted"
    print(f"     ok — {llm.usage.summary()}")

    print("\nAll three live paths work. The adapter is wired correctly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
