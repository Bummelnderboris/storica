"""
The front-door brief (`novels/<slug>/00_input/brief.yaml`).

This is the **only** human input to a run (DESIGN D3): a light brief of thoughts, question-lines
and nudges. It is also **immutable ground truth** (principle 5) — nothing downstream may edit it;
adjudication resolves conflicts *toward* it. Loading is therefore read-only by construction.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field

PathLike = Union[str, Path]

BRIEF_FILE = "brief.yaml"


class Brief(BaseModel):
    """What the creator supplies. Everything else is generated."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    author_id: str
    spark: str = ""                                       # the seed thought / situation
    thoughts: str = ""                                    # free-text musings, unstructured
    question_lines: List[str] = Field(default_factory=list)  # the creator's own questions
    nudges: List[str] = Field(default_factory=list)       # steer toward / away
    forbidden: List[str] = Field(default_factory=list)    # hard "no" list → canon.constraints
    language: str = "en"
    chapter_count: Optional[int] = None
    title_hint: str = ""

    def prompt_block(self) -> str:
        """The brief as the stages see it. Kept verbatim — this is ground truth."""
        parts = [f"# Creator brief (IMMUTABLE GROUND TRUTH)\n\nSpark: {self.spark or '(none given)'}"]
        if self.thoughts:
            parts.append(f"\nThoughts:\n{self.thoughts}")
        if self.question_lines:
            parts.append("\nCreator's question-lines:\n" + "\n".join(f"- {q}" for q in self.question_lines))
        if self.nudges:
            parts.append("\nNudges:\n" + "\n".join(f"- {n}" for n in self.nudges))
        if self.forbidden:
            parts.append("\nForbidden (hard no):\n" + "\n".join(f"- {f}" for f in self.forbidden))
        parts.append(
            f"\nLanguage: {self.language}"
            + (f"\nTarget chapter count: {self.chapter_count}" if self.chapter_count else "")
        )
        return "\n".join(parts)


def load_brief(input_dir: PathLike) -> Brief:
    """Load `00_input/brief.yaml`."""
    path = Path(input_dir) / BRIEF_FILE
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return Brief.model_validate(data)


def save_brief(brief: Brief, input_dir: PathLike) -> Path:
    """Write the brief once, at novel creation. Refuses to overwrite: ground truth is frozen."""
    input_dir = Path(input_dir)
    input_dir.mkdir(parents=True, exist_ok=True)
    path = input_dir / BRIEF_FILE
    if path.exists():
        raise FileExistsError(f"{path} already exists — the brief is immutable ground truth")
    path.write_text(yaml.safe_dump(brief.model_dump(), sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path
