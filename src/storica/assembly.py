"""
Assembly: the drafted chapters become `novels/<slug>/novel.md` (DESIGN §3, P6).

Deliberately the dumbest step in the pipeline. It concatenates what is on disk and refuses to
improve it: the prose was written from canon, checked, and repaired under a bounded loop, so any
editing here would be an unchecked agent-free rewrite of verified text.

Two rules carry the weight, both from the §6.5 safety rails:

- **A quarantined chapter is never shipped.** A unit that exhausted its repair budget is excluded
  from `novel.md` rather than smuggled into the book because it was the last step and nobody was
  watching. It leaves a visible hole, and the hole is reported.
- **A hole is an issue, not a formatting problem.** A chapter the arc planned but that has no draft
  is blocking. A gap in the *middle* is worse than a missing tail — a truncated book merely stops,
  a holed book asks the reader to cross a discontinuity — so the two are reported apart, and the
  Final Auditor (`checkers/auditor.py`) is handed the difference rather than left to infer it.

The result is a value, not a side effect: `assemble_novel` decides what the book is, `save_novel`
writes it. The caller records the issues in `05_reports/` (see `reports.write_run_report`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union

from .canon import Issue, Severity, StoryModel
from .drafts import drafted_chapters, load_chapter_draft
from .plan import MacroArc
from .reports import QuarantineLog

PathLike = Union[str, Path]

NOVEL_FILE = "novel.md"

# A rule between chapters: the drafts already open with their own `# <title>`, so the separator only
# has to make the seam unmistakable without touching either side of it.
CHAPTER_SEPARATOR = "\n\n---\n\n"


def chapter_unit(chapter: int) -> str:
    """The unit label chapters are quarantined under — must match the `chNN` prefix `stages/prose` writes under."""
    return f"ch{chapter:02d}"


@dataclass
class AssemblyResult:
    """What the book turned out to be, and everything wrong with that."""

    text: str
    chapters: List[int] = field(default_factory=list)   # included, in reading order
    excluded: List[int] = field(default_factory=list)   # quarantined or never drafted
    issues: List[Issue] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        return not any(i.severity == Severity.BLOCKING for i in self.issues)


def assemble_novel(
    *,
    canon: StoryModel,
    arc: MacroArc,
    drafts_dir: PathLike,
    quarantine: Optional[QuarantineLog] = None,
    title: str = "",
) -> AssemblyResult:
    """
    Build the finished book from `03_drafts/`, excluding anything that must not ship.

    `canon` is taken for the constraints it carries (and so the caller cannot assemble a book
    without the canon it was written from); the prose itself is never re-derived from it.
    """
    planned = list(range(1, arc.chapter_count + 1))
    drafted = drafted_chapters(drafts_dir)

    quarantined = [
        n for n in drafted if quarantine is not None and quarantine.is_quarantined(chapter_unit(n))
    ]
    included = [n for n in drafted if n not in set(quarantined)]
    missing = [n for n in planned if n not in set(drafted)]

    issues: List[Issue] = []

    for n in quarantined:
        issues.append(Issue(
            "assembly.quarantined", Severity.BLOCKING,
            f"chapter {n} was quarantined and is excluded from novel.md — the book has a hole where "
            f"it was; see 05_reports/quarantine.jsonl for why it could not be made correct",
            chapter_unit(n),
        ))

    last_included = included[-1] if included else 0
    for n in [m for m in missing if m < last_included]:
        issues.append(Issue(
            "assembly.gap", Severity.BLOCKING,
            f"chapter {n} is planned but has no draft, and the book continues past it: this is a gap "
            f"in the middle of the book, which is worse than a missing ending — the reader is asked "
            f"to cross a discontinuity rather than merely stop early",
            chapter_unit(n),
        ))
    tail = [m for m in missing if m > last_included]
    if tail:
        issues.append(Issue(
            "assembly.missing_ending", Severity.BLOCKING,
            f"the book stops at chapter {last_included} of {arc.chapter_count}: chapter"
            f"{'s' if len(tail) > 1 else ''} {', '.join(str(n) for n in tail)} "
            f"{'were' if len(tail) > 1 else 'was'} planned but never drafted",
            chapter_unit(tail[0]),
        ))

    for n in included:
        if n not in planned:
            issues.append(Issue(
                "assembly.unplanned", Severity.WARNING,
                f"chapter {n} has a draft but the arc plans only {arc.chapter_count} chapters — it is "
                f"included (dropping written prose silently would be worse), but plan and drafts disagree",
                chapter_unit(n),
            ))

    # Prose is passed through verbatim; only the whitespace around a draft is normalised, so the
    # separator lands the same way after every chapter.
    body = CHAPTER_SEPARATOR.join(
        load_chapter_draft(drafts_dir, n).strip() for n in included
    )
    text = f"# {title.strip()}\n\n{body}" if title.strip() else body
    if text:
        text += "\n"

    return AssemblyResult(
        text=text,
        chapters=included,
        excluded=sorted(set(quarantined) | set(missing)),
        issues=issues,
    )


def save_novel(text: str, novel_dir: PathLike) -> Path:
    """Write `novel.md` at the novel root — the one artifact meant for a reader, not an agent."""
    path = Path(novel_dir) / NOVEL_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
