"""
The agents, read from `agents/*.md` — one file per agent, instructions and wiring together.

Every agent's system prompt used to be a string constant in the module that called it, spread over
fifteen files, and its model a row in a dict in `llm.py`. To find out what an agent was told you had
to read the code, and to tune it you had to edit the code. Quality lives in those instructions, so
they belong where a person can see and change them without touching Python.

A file is YAML frontmatter followed by the system prompt:

    ---
    id: voice                 # the name the code asks for; also the key of the model table
    name: Author-voice reader
    model: sonnet             # default alias for this agent (see `llm.MODELS`)
    ...                       # descriptive fields: read by `storica map`, never by the pipeline
    ---
    You are an Author-Voice checker ...

The body is the system prompt byte for byte. Instructions an agent is handed *inside* its prompt
(a reader's rubric, the writer's "before you write" block) follow it as named sections, each opened
by a line `<!-- name -->` after a blank line; the code asks for them with `block(id, name)`.
Anywhere in the body, `{{include: <name>}}` is replaced by
`agents/_shared/<name>.md`. Text shared between agents (the invention policy, read by the writer
*and* the reader that judges it) lives there once, so the two can never drift apart again.

Byte-for-byte matters: the replay driver keys every recorded answer on the exact system prompt, so
editing a file here makes the affected calls ask again. That is the intended behaviour — a changed
instruction is a different call — and it is also how a pure move is verified: the P6 run replays
with zero new requests.

The directory is `agents/` at the repository root, next to `authors/`; `STORICA_AGENTS` overrides it.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

import yaml

AGENTS_DIR = Path(os.environ.get("STORICA_AGENTS", Path(__file__).resolve().parents[2] / "agents"))
SHARED_DIR = "_shared"

_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
_INCLUDE = re.compile(r"\{\{include: *([a-z0-9_-]+) *\}\}")
_SECTION = re.compile(r"\n\n<!-- ([a-z0-9_-]+) -->\n")


@dataclass(frozen=True)
class Agent:
    id: str
    name: str
    model: str
    system: str
    #: Named sections after the system prompt: instructions the code places inside the prompt.
    blocks: Dict[str, str] = field(default_factory=dict, compare=False)
    #: Everything else in the frontmatter: family, step, fires, reads, writes, authority, input,
    #: trace. Descriptive only — the map renders it; the pipeline never branches on it.
    meta: Dict = field(default_factory=dict, compare=False)
    path: Path = Path()


def _read_body(text: str) -> str:
    # Files end with one newline for the editor's sake; the prompt itself does not.
    return text[:-1] if text.endswith("\n") else text


def shared(name: str, root: Path = None) -> str:
    """A block of instructions shared by several agents, from `agents/_shared/<name>.md`."""
    path = Path(root or AGENTS_DIR) / SHARED_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"shared agent block {name!r} not found at {path}")
    return _read_body(path.read_text(encoding="utf-8"))


def parse_agent(path: Path, root: Path = None) -> Agent:
    text = path.read_text(encoding="utf-8")
    m = _FRONTMATTER.match(text)
    if not m:
        raise ValueError(f"{path}: an agent file starts with a '---' YAML frontmatter block")
    meta = yaml.safe_load(m.group(1)) or {}
    for key in ("id", "name", "model"):
        if not meta.get(key):
            raise ValueError(f"{path}: frontmatter needs {key!r}")
    if meta["id"] != path.stem:
        raise ValueError(f"{path}: id {meta['id']!r} must match the file name")
    body = _INCLUDE.sub(lambda i: shared(i.group(1), root or path.parent), _read_body(text[m.end():]))
    parts = _SECTION.split(body)
    body, blocks = parts[0], dict(zip(parts[1::2], parts[2::2]))
    if not body.strip():
        raise ValueError(f"{path}: the body (the agent's system prompt) is empty")
    rest = {k: v for k, v in meta.items() if k not in ("id", "name", "model")}
    return Agent(id=meta["id"], name=meta["name"], model=meta["model"], system=body, blocks=blocks, meta=rest, path=path)


@lru_cache(maxsize=None)
def _load(root: str) -> Dict[str, Agent]:
    base = Path(root)
    if not base.is_dir():
        raise FileNotFoundError(
            f"no agents directory at {base} — the agent instructions live there (set STORICA_AGENTS "
            f"to point elsewhere)"
        )
    agents = {}
    for path in sorted(base.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        a = parse_agent(path, base)
        agents[a.id] = a
    return agents


def all_agents(root: Path = None) -> List[Agent]:
    """Every agent, ordered as the pipeline meets them (frontmatter `order`)."""
    return sorted(_load(str(root or AGENTS_DIR)).values(), key=lambda a: (a.meta.get("order", 999), a.id))


def agent(agent_id: str, root: Path = None) -> Agent:
    agents = _load(str(root or AGENTS_DIR))
    if agent_id not in agents:
        raise KeyError(f"no agent {agent_id!r} in {root or AGENTS_DIR} (have: {', '.join(sorted(agents))})")
    return agents[agent_id]


def system(agent_id: str) -> str:
    """The system prompt of one agent — what every call site passes as `system=`."""
    return agent(agent_id).system


def block(agent_id: str, name: str) -> str:
    """A named section of one agent's file — instructions the code places inside the prompt."""
    a = agent(agent_id)
    if name not in a.blocks:
        raise KeyError(f"agents/{agent_id}.md has no section <!-- {name} --> (has: {', '.join(a.blocks) or 'none'})")
    return a.blocks[name]
