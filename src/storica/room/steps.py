"""
The writers' room: the story is developed with the creator, one step at a time.

The autonomous pipeline (`storica run`) takes a brief and hands back a book. The room works the way
the creator asked for instead: an agent drafts a document, the story editor reviews it, the creator
reads both and answers, and the agent revises. Nothing moves to the next step until the creator
approves. Each call goes to a fresh agent; the session that talks with the creator relays and
records, and never writes the story itself (see `.claude/skills/develop/SKILL.md`).

One round of a step is `advance()`:

- no document yet → the writer drafts (for the pitch: three options), the editor reviews;
- new notes from the creator → the writer revises with them, the editor reviews the revision, and
  the notes move into the document's decisions;
- otherwise there is nothing to do until the creator says something.

The document is written only once every call of the round has returned. Under the replay driver a
round can pause for answers any number of times and resumes from the same state: the prompts are a
function of the document on disk, which has not changed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from ..agents import block, system
from ..authors import AuthorModel
from ..brief import Brief
from ..llm import StructuredLLM, stage_model
from ..stages.prose.prompts import _LANGUAGE_NAMES
from ..trace import Tracer
from . import document
from .document import Document, labels

HISTORY_DIR = "_history"
TRACE_DIR = "_trace"
SESSION_DIR = "_session"


@dataclass(frozen=True)
class Step:
    id: str
    number: int
    title: str
    writer: str
    editor: str

    @property
    def filename(self) -> str:
        return f"{self.number:02d}_{self.id}.md"


#: The room's steps in order. R3 adds characters, storyline, scene cards and editor's notes here.
STEPS: List[Step] = [
    Step(id="pitch", number=1, title="Pitch", writer="pitch_writer", editor="story_editor"),
]


def step(step_id: str) -> Step:
    for s in STEPS:
        if s.id == step_id:
            return s
    raise KeyError(f"no step {step_id!r} (steps: {', '.join(s.id for s in STEPS)})")


class Assessment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(description="The option or pitch this is about, labelled as the document labels it.")
    strengths: str = Field(description="What works, concretely, with quotes.")
    risks: str = Field(description="What does not work or may fail, concretely, with quotes.")


class EditorReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(description="Three to five plain sentences for the creator.")
    assessments: List[Assessment]
    recommendation: str = Field(description="What to do next, in one or two sentences.")
    questions: List[str] = Field(description="At most two real choices for the creator, in everyday words.")


def render_review(review: EditorReview, language: str) -> str:
    lab = labels(language)
    lines = [f"## {lab['editor']}", "", f"**{lab['summary']}:** {review.summary}", "", f"### {lab['assessment']}"]
    for a in review.assessments:
        lines += ["", f"**{a.label}**", f"- {lab['strengths']}: {a.strengths}", f"- {lab['risks']}: {a.risks}"]
    lines += ["", f"**{lab['recommendation']}:** {review.recommendation}"]
    if review.questions:
        lines += ["", f"### {lab['questions']}"] + [f"{i}. {q}" for i, q in enumerate(review.questions, 1)]
    return "\n".join(lines)


def _language(brief: Brief) -> str:
    return _LANGUAGE_NAMES.get(brief.language, brief.language)


def _context(brief: Brief, author: AuthorModel) -> str:
    return f"""{brief.prompt_block()}

{author.conception_block()}

Write in {_language(brief)}. The creator's brief above is where they started; where their notes or
decisions below say otherwise, the notes win."""


def _decisions_block(doc: Document) -> str:
    if not doc.decisions:
        return ""
    return "# The creator's decisions so far\n" + "\n".join(f"- {d}" for d in doc.decisions) + "\n\n"


def pitch_prompt(brief: Brief, author: AuthorModel, doc: Document) -> str:
    """The writer's input: options on the first round, a revision on every later one."""
    if not doc.content:
        return f"{_context(brief, author)}\n\n{block('pitch_writer', 'options')}"
    return f"""{_context(brief, author)}

{_decisions_block(doc)}# The current document (version {doc.version})
{doc.content}

# The editor's review of that version
{doc.editor}

# The creator's new notes (work in every one of them)
{doc.notes}

{block('pitch_writer', 'revise')}"""


def review_prompt(brief: Brief, author: AuthorModel, doc: Document, content: str) -> str:
    return f"""{_context(brief, author)}

{_decisions_block(doc)}# The document to review
{content}

{block('story_editor', 'review')}"""


@dataclass
class Outcome:
    doc: Document
    path: Path
    changed: bool
    message: str


async def advance(
    *,
    novel_dir: Path,
    step_id: str,
    brief: Brief,
    author: AuthorModel,
    llm: StructuredLLM,
    tracer: Optional[Tracer] = None,
) -> Outcome:
    s = step(step_id)
    path = novel_dir / s.filename
    doc = document.load(path, s.id, brief.language)
    tracer = tracer or Tracer(novel_dir / TRACE_DIR)

    if doc.content and not doc.notes:
        state = "approved" if doc.approved else "waiting for the creator's notes or approval"
        return Outcome(doc, path, False, f"{path.name} v{doc.version}: {state}")

    first = not doc.content
    stage = f"{s.id}_options" if first else f"{s.id}_revise_v{doc.version + 1}"
    prompt = pitch_prompt(brief, author, doc)
    writer_system, writer_model = system(s.writer), stage_model(s.writer)
    content = await llm.generate(prompt=prompt, system=writer_system, model=writer_model)
    tracer.record(stage, prompt=prompt, system=writer_system, model=writer_model, artifact=content)

    rprompt = review_prompt(brief, author, doc, content)
    editor_system, editor_model = system(s.editor), stage_model(s.editor)
    review = await llm.parse(prompt=rprompt, schema=EditorReview, system=editor_system, model=editor_model)
    tracer.record(
        f"{s.id}_review_v{doc.version + 1}", prompt=rprompt, system=editor_system, model=editor_model,
        artifact=review, note=review.recommendation,
    )

    new = Document(
        step=s.id,
        language=brief.language,
        status="open",
        version=doc.version + 1,
        content=content.strip(),
        editor=render_review(review, brief.language),
        decisions=doc.decisions + ([f"v{doc.version} → v{doc.version + 1}: {' '.join(doc.notes.split())}"] if doc.notes else []),
        notes="",
    )
    document.save(new, path, novel_dir / HISTORY_DIR)
    return Outcome(new, path, True, f"{path.name} v{new.version} ready: {len(review.questions)} question(s) from the editor")


def add_note(novel_dir: Path, step_id: str, language: str, note: str) -> Document:
    """Append the creator's words to the notes section, verbatim. Reopens an approved step."""
    s = step(step_id)
    path = novel_dir / s.filename
    doc = document.load(path, s.id, language)
    if not doc.content:
        raise ValueError(f"{path.name} does not exist yet; run the step first")
    doc.notes = (doc.notes + "\n" if doc.notes else "") + "\n".join(f"- {line}" for line in note.strip().split("\n") if line.strip())
    doc.status = "open"
    document.save(doc, path, novel_dir / HISTORY_DIR)
    return doc


def approve(novel_dir: Path, step_id: str, language: str) -> Document:
    s = step(step_id)
    path = novel_dir / s.filename
    doc = document.load(path, s.id, language)
    if not doc.content:
        raise ValueError(f"{path.name} does not exist yet; there is nothing to approve")
    if doc.notes:
        raise ValueError(f"{path.name} has notes that are not worked in yet; run the step, or remove them")
    doc.status = "approved"
    document.save(doc, path, novel_dir / HISTORY_DIR)
    return doc


def overview(novel_dir: Path, language: str) -> List[str]:
    lines = []
    for s in STEPS:
        path = novel_dir / s.filename
        doc = document.load(path, s.id, language)
        if not doc.content:
            lines.append(f"{s.number}. {s.title}: not started")
        else:
            pending = " · new notes waiting" if doc.notes else ""
            lines.append(f"{s.number}. {s.title}: v{doc.version}, {doc.status}{pending} ({s.filename})")
    return lines
