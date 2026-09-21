"""
The author model (DESIGN §5 stage 0).

The author is a **generative driver**, not a paint job (principle 6): their obsessions and
question-lines select *which story gets told*, so Conception needs them as prompt material, not
just the Voice checker. This loads `authors/<id>/` into one object with a renderable prompt block.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Union

import yaml

PathLike = Union[str, Path]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


def _prompt_body(markdown: str) -> str:
    """
    An author file as prompt material: without its file title, its note on who reads it, or its
    blockquoted asides.

    The asides are the reason this exists. `nudges.md` ends with a note quoting lines from the v1
    run's own prose as examples of what worked and what failed. That is documentation for people;
    handed to the v2 *writer*, it is the previous book's sentences offered as a model to copy, and a
    P6 comparison in which v2 was shown v1's prose is not a comparison.
    """
    lines = markdown.strip().splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    first_section = next((i for i, line in enumerate(lines) if line.startswith("## ")), None)
    if first_section is not None:
        lines = lines[first_section:]
    return "\n".join(line for line in lines if not line.lstrip().startswith(">")).strip()


@dataclass
class AuthorModel:
    id: str
    name: str
    language: str
    profile: dict          # parsed profile.yaml
    question_lines: str    # question_lines.md — the obsessions that drive conception
    nudges: str            # nudges.md — steer toward / away (voice)
    impression: str        # impression.md — what it feels like to read them

    @property
    def philosophy(self) -> dict:
        return self.profile.get("philosophy", {}) or {}

    @property
    def central_obsession(self) -> str:
        return str(self.philosophy.get("central_obsession", "")).strip()

    @property
    def worldview(self) -> str:
        return str(self.philosophy.get("worldview", "")).strip()

    def conception_block(self) -> str:
        """The author material Conception (stage 1) reasons with."""
        return f"""# Author: {self.name} ({self.id})

## Worldview
{self.worldview}

## Central obsession
{self.central_obsession}

## Question-lines (the questions this author keeps asking)
{self.question_lines}

## What it feels like to read them
{self.impression}"""

    def voice_block(self) -> str:
        """The author material voice-sensitive stages need (kept separate so it can be cached)."""
        return f"# Author voice: {self.name}\n\n{self.nudges}"

    def writer_block(self) -> str:
        """
        Everything the *prose* agent needs to write as this author — not just what it must avoid.

        For a long time the writer got `voice_block()` alone: ~200 words of steer-toward and
        steer-away, while the voice and vitality readers judging it were also handed the impression
        material. The writer was graded against a picture of the author it had never been shown. This
        block is the craft the profile actually records — sentence patterns, register, dialogue,
        openings and endings, register samples — plus the nudges and the impression, so the maker
        knows at least as much about the author as the judges do.

        Plan stages keep `voice_block()`: they decide what happens, not how it sounds, and the
        replay cache keys on their exact prompts.
        """
        language = self.profile.get("language", {}) or {}
        structure = self.profile.get("structure", {}) or {}

        def items(values) -> str:
            return "\n".join(f"- {v}" for v in (values or [])) or "- (none recorded)"

        def text(value) -> str:
            return str(value or "").strip() or "(none recorded)"

        samples = "\n\n".join(
            f"[{e.get('category', 'sample')}] {str(e.get('text', '')).strip()}\n"
            f"— why it works: {str(e.get('annotation', '')).strip()}"
            for e in (self.profile.get("examples") or [])
            if str(e.get("text", "")).strip()
        ) or "(none recorded)"

        return f"""# Writing as {self.name}

{_prompt_body(self.nudges)}

## Sentences
{items(language.get('sentence_patterns'))}

## Vocabulary and register
{text(language.get('vocabulary'))}
{text(language.get('register'))}

## Signature moves
{items(language.get('markers'))}

## Dialogue
{text(language.get('dialogue_style'))}

## Scenes, openings, endings
{text(structure.get('chapter_patterns'))}
{text(structure.get('openings'))}
{text(structure.get('endings'))}

## Register samples
These show the temperature of the prose, not material to reuse. Some are paraphrases rather than
verbatim quotations. Never copy a sentence or a situation from them.

{samples}

## What it feels like to read {self.name}
{_prompt_body(self.impression)}"""


def load_author(author_id: str, authors_root: PathLike) -> AuthorModel:
    """Load `authors/<author_id>/` into an AuthorModel."""
    root = Path(authors_root) / author_id
    profile_path = root / "profile.yaml"
    if not profile_path.exists():
        raise FileNotFoundError(f"no author profile at {profile_path}")

    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
    meta = profile.get("metadata", {}) or {}

    return AuthorModel(
        id=author_id,
        name=meta.get("name", author_id),
        language=meta.get("primary_language", "en"),
        profile=profile,
        question_lines=_read(root / "question_lines.md"),
        nudges=_read(root / "nudges.md"),
        impression=_read(root / "impression.md"),
    )
