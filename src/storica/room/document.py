"""
A writers'-room document: the thing the creator reads, edits and steers with.

In the autonomous pipeline every stage wrote JSON for the next stage and nothing for a person. Here
the document *is* the hand-off: the next agent reads the text the creator last saw, including any
edits they made to it by hand. So the format is Markdown first, with just enough structure for the
code to find its way around:

    ---
    step: pitch
    status: open            # open | approved
    version: 2
    ---
    <the agent's text: the part the story is made of, freely editable>

    <!-- storica:editor -->
    ## Lektorat             the story editor's review of this version (replaced every round)

    <!-- storica:decisions -->
    ## Deine bisherigen Vorgaben     every note the creator gave, by version (append-only)

    <!-- storica:notes -->
    ## Deine Notizen        new notes, not yet worked in — written by hand or by `storica develop --note`

A revision reads the notes, moves them into the decisions, and clears them. Everything before the
first marker is the agent's text; the markers are HTML comments, so they are invisible when the file
is rendered. Headings of the code-written sections follow the novel's language.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import yaml

SECTIONS = ("editor", "decisions", "notes")
_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
_MARKER = re.compile(r"^<!-- storica:(editor|decisions|notes) -->\n", re.M)
_COMMENT = re.compile(r"<!--.*?-->", re.S)

LABELS = {
    "de": {
        "editor": "Lektorat", "summary": "Zusammenfassung", "assessment": "Einschätzung",
        "strengths": "Stärken", "risks": "Risiken", "recommendation": "Empfehlung",
        "questions": "Fragen an dich", "decisions": "Deine bisherigen Vorgaben",
        "notes": "Deine Notizen",
        "notes_hint": "Schreib hier, was sich ändern soll, oder sag es in der Session. "
                      "Beim nächsten Durchgang wird es eingearbeitet.",
    },
    "en": {
        "editor": "Editor's review", "summary": "Summary", "assessment": "Assessment",
        "strengths": "Strengths", "risks": "Risks", "recommendation": "Recommendation",
        "questions": "Questions for you", "decisions": "Your decisions so far",
        "notes": "Your notes",
        "notes_hint": "Write what should change here, or say it in the session. "
                      "The next round works it in.",
    },
}


def labels(language: str) -> dict:
    return LABELS.get(language, LABELS["en"])


@dataclass
class Document:
    step: str
    language: str
    status: str = "open"
    version: int = 0
    content: str = ""
    editor: str = ""
    decisions: List[str] = field(default_factory=list)
    notes: str = ""

    @property
    def approved(self) -> bool:
        return self.status == "approved"

    def render(self) -> str:
        lab = labels(self.language)
        front = yaml.safe_dump(
            {"step": self.step, "status": self.status, "version": self.version},
            sort_keys=False, allow_unicode=True,
        )
        decisions = "\n".join(f"- {d}" for d in self.decisions)
        parts = [
            f"---\n{front}---\n",
            self.content.strip() + "\n",
            "<!-- storica:editor -->\n" + (self.editor.strip() + "\n" if self.editor.strip() else f"## {lab['editor']}\n"),
            f"<!-- storica:decisions -->\n## {lab['decisions']}\n" + (decisions + "\n" if decisions else ""),
            f"<!-- storica:notes -->\n## {lab['notes']}\n<!-- {lab['notes_hint']} -->\n"
            + (self.notes.strip() + "\n" if self.notes.strip() else ""),
        ]
        return "\n".join(parts)


def _strip_heading(text: str) -> str:
    lines = text.strip("\n").split("\n")
    if lines and lines[0].startswith("## "):
        lines = lines[1:]
    return "\n".join(lines).strip()


def parse(text: str, language: str) -> Document:
    m = _FRONTMATTER.match(text)
    if not m:
        raise ValueError("a writers'-room document starts with a '---' frontmatter block")
    meta = yaml.safe_load(m.group(1)) or {}
    body = text[m.end():]

    pieces = _MARKER.split(body)
    content, sections = pieces[0], dict(zip(pieces[1::2], pieces[2::2]))
    decisions = [
        line[2:].strip() for line in _strip_heading(sections.get("decisions", "")).split("\n")
        if line.startswith("- ")
    ]
    notes = _COMMENT.sub("", _strip_heading(sections.get("notes", ""))).strip()
    return Document(
        step=str(meta.get("step", "")),
        language=language,
        status=str(meta.get("status", "open")),
        version=int(meta.get("version", 0) or 0),
        content=content.strip(),
        editor=sections.get("editor", "").strip(),
        decisions=decisions,
        notes=notes,
    )


def load(path: Path, step: str, language: str) -> Document:
    if not path.exists():
        return Document(step=step, language=language)
    return parse(path.read_text(encoding="utf-8"), language)


def save(doc: Document, path: Path, history_dir: Path) -> None:
    """Write `doc`, first archiving the version it replaces as `<history>/<name>.v<N>.md`."""
    if path.exists():
        old = parse(path.read_text(encoding="utf-8"), doc.language)
        if old.version and old.version != doc.version:
            history_dir.mkdir(parents=True, exist_ok=True)
            (history_dir / f"{path.stem}.v{old.version}.md").write_text(
                path.read_text(encoding="utf-8"), encoding="utf-8"
            )
    path.write_text(doc.render(), encoding="utf-8")
