"""
The replay driver — run the pipeline with no API key, answered by an agent or a human.

The problem it solves: the pipeline is a long chain of model calls, but during development the
model is *you* (a Claude Code session on a subscription), not an API. You cannot block a running
process waiting for a person to type a chapter.

So this adapter never blocks. For each call it computes a stable key from
(model, system, prompt, schema); if `responses/<key>.*` exists it replays it, and if it does not,
it writes a readable request file and raises `ResponseNeeded`. The runner stops, the answer gets
written to disk, the runner is started again — every already-answered call replays instantly from
cache and the run continues from exactly where it stopped.

Two properties matter:
- **The prompts are the real prompts.** Nothing is mocked; a run driven this way exercises the same
  prompt text, the same gates, and the same repair loops that production will.
- **Deterministic resume.** The key is content-addressed, so re-running after an edit replays the
  unchanged prefix and only asks for what actually changed.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Type, TypeVar, Union

from pydantic import BaseModel, ValidationError

from ..llm import StructuredLLM, Usage, resolve_model

T = TypeVar("T", bound=BaseModel)
PathLike = Union[str, Path]

REQUESTS_DIR = "requests"
RESPONSES_DIR = "responses"


class MalformedResponse(RuntimeError):
    """
    A recorded answer does not match the schema it was asked for.

    Raised in place of a bare pydantic error because the useful information is *which file* to
    correct — a driven run answers hundreds of calls and a stack trace names none of them.
    """

    def __init__(self, response_path: Path, schema_name: str, detail: str):
        self.response_path = response_path
        self.schema_name = schema_name
        super().__init__(
            f"the recorded answer does not match {schema_name}\n"
            f"  file:  {response_path}\n"
            f"  error: {detail}\n"
            f"fix the file (or delete it to be asked again) and run the same command."
        )


class ResponseNeeded(RuntimeError):
    """
    A call has no recorded answer yet. Not an error condition — the normal way a driven run pauses.
    """

    def __init__(self, key: str, stage: str, request_path: Path, response_path: Path, is_text: bool):
        self.key = key
        self.stage = stage
        self.request_path = request_path
        self.response_path = response_path
        self.is_text = is_text
        kind = "markdown prose" if is_text else "JSON matching the schema in the request"
        super().__init__(
            f"awaiting response for '{stage}' [{key}]\n"
            f"  read:  {request_path}\n"
            f"  write: {response_path}  ({kind})\n"
            f"then run the same command again — answered calls replay from cache."
        )


@dataclass
class PendingRequest:
    key: str
    stage: str
    request_path: Path
    response_path: Path


class ReplayLLM(StructuredLLM):
    """
    A `StructuredLLM` backed by files on disk instead of an API.

    `session_dir` holds `requests/` and `responses/`. Answers are written by whoever is playing the
    model; the pipeline neither knows nor cares.
    """

    def __init__(self, session_dir: PathLike, *, stage_hint: str = "call"):
        self.session_dir = Path(session_dir)
        self.requests_dir = self.session_dir / REQUESTS_DIR
        self.responses_dir = self.session_dir / RESPONSES_DIR
        self.requests_dir.mkdir(parents=True, exist_ok=True)
        self.responses_dir.mkdir(parents=True, exist_ok=True)
        self.stage_hint = stage_hint
        self.replayed = 0
        self.requested = 0
        self.usage = Usage()  # a replayed call cost nothing; the counter exists so callers need not care

    # -- keying ---------------------------------------------------------------------------------

    @staticmethod
    def _key(*, model: str, system: Optional[str], prompt: str, schema_name: str, schema_json: str) -> str:
        payload = "\x1f".join([resolve_model(model), system or "", prompt, schema_name, schema_json])
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def _draw_key(self, base: str, draw: int) -> str:
        """
        Give each *repeated* draw of an identical call its own cache slot.

        Content addressing is right for the whole pipeline except where it deliberately makes the
        same call more than once, and it does that in two places:

        - **generate-and-select** draws k candidates from one prompt (`stages/prose/selection.py`),
          so the spread comes from sampling rather than from asking for k different things;
        - **consensus sampling** draws one checker k times (`checkers/consensus.py`) and blocks on
          a majority, because a single verdict flags clean text ~20% of the time (calibration C4).

        Keyed on content alone, all k collapse onto one cached answer: the selector chooses between
        k copies of one draft, and majority-of-3 becomes one verdict counted three times. Both
        mechanisms silently do nothing, and — worse — they look like they worked, because the trace
        deduplicates the identical records.

        So a repeated call gets an occurrence suffix, taken from the `draw` index the caller passes.
        It is explicit rather than a counter kept here precisely so the fan-outs can run
        concurrently: draw 2 resolves to slot 2 whichever draw happens to finish first, and a
        resumed run replays every slot regardless of completion order.
        """
        return base if draw <= 1 else f"{base}-{draw}"

    def _paths(self, key: str, *, is_text: bool) -> tuple[Path, Path]:
        suffix = "md" if is_text else "json"
        return (
            self.requests_dir / f"{key}.request.md",
            self.responses_dir / f"{key}.response.{suffix}",
        )

    # -- request writing ------------------------------------------------------------------------

    def _write_request(
        self,
        *,
        key: str,
        stage: str,
        model: str,
        system: Optional[str],
        prompt: str,
        schema: Optional[Type[BaseModel]],
        request_path: Path,
        response_path: Path,
    ) -> None:
        schema_block = (
            f"""
## Required response schema (`{schema.__name__}`)

Write **only** a JSON object matching this schema to `{response_path.name}`:

```json
{json.dumps(schema.model_json_schema(), indent=2, ensure_ascii=False)}
```
"""
            if schema is not None
            else f"""
## Required response

Write the prose to `{response_path.name}` as markdown. No commentary, no fences — just the text.
"""
        )
        request_path.write_text(
            f"""# Request `{key}` — {stage}

- model: `{resolve_model(model)}`
- answer file: `{response_path}`

## System prompt

{system or "(none)"}

## Prompt

{prompt}
{schema_block}""",
            encoding="utf-8",
        )

    # -- port ------------------------------------------------------------------------------------

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
        schema_json = json.dumps(schema.model_json_schema(), sort_keys=True)
        key = self._draw_key(self._key(
            model=model, system=system, prompt=prompt,
            schema_name=schema.__name__, schema_json=schema_json,
        ), draw)
        request_path, response_path = self._paths(key, is_text=False)

        if response_path.exists():
            self.replayed += 1
            try:
                return schema.model_validate_json(response_path.read_text(encoding="utf-8"))
            except ValidationError as exc:
                raise MalformedResponse(response_path, schema.__name__, str(exc)) from exc

        self.requested += 1
        stage = f"{self.stage_hint}:{schema.__name__}"
        self._write_request(
            key=key, stage=stage, model=model, system=system, prompt=prompt, schema=schema,
            request_path=request_path, response_path=response_path,
        )
        raise ResponseNeeded(key, stage, request_path, response_path, is_text=False)

    async def generate(
        self,
        *,
        prompt: str,
        system: Optional[str] = None,
        model: str = "opus",
        max_tokens: int = 32000,
        draw: int = 1,
    ) -> str:
        key = self._draw_key(
            self._key(model=model, system=system, prompt=prompt, schema_name="<text>", schema_json=""),
            draw,
        )
        request_path, response_path = self._paths(key, is_text=True)

        if response_path.exists():
            self.replayed += 1
            return response_path.read_text(encoding="utf-8")

        self.requested += 1
        stage = f"{self.stage_hint}:prose"
        self._write_request(
            key=key, stage=stage, model=model, system=system, prompt=prompt, schema=None,
            request_path=request_path, response_path=response_path,
        )
        raise ResponseNeeded(key, stage, request_path, response_path, is_text=True)

    # -- introspection ---------------------------------------------------------------------------

    def pending(self) -> List[PendingRequest]:
        """Requests written but not yet answered."""
        out: List[PendingRequest] = []
        for request_path in sorted(self.requests_dir.glob("*.request.md")):
            key = request_path.name.split(".")[0]
            answered = any((self.responses_dir / f"{key}.response.{ext}").exists() for ext in ("json", "md"))
            if not answered:
                is_text = ":prose" in request_path.read_text(encoding="utf-8").split("\n", 1)[0]
                out.append(PendingRequest(
                    key=key,
                    stage=request_path.read_text(encoding="utf-8").split("—", 1)[-1].split("\n", 1)[0].strip(),
                    request_path=request_path,
                    response_path=self.responses_dir / f"{key}.response.{'md' if is_text else 'json'}",
                ))
        return out
