"""
Command line entry point.

Two ways to supply the model, and the choice is the whole point of this file:

- `--driver anthropic` — the real API, for an unattended production run.
- `--driver replay` — no API key. Every call that has no recorded answer writes a request file and
  stops the run; you (or an agent) write the answer and run the same command again. The pipeline
  is identical either way, so a book produced this way validates the real prompts.

Usage:
    storica new    novels/der-chrachen --author duerrenmatt
    storica run    novels/der-chrachen --driver replay
    storica status novels/der-chrachen
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from .brief import Brief, save_brief
from .canon import load_canon
from .drafts import drafted_chapters
from .drivers import MalformedResponse, ReplayLLM, ResponseNeeded
from .llm import AnthropicStructuredLLM, StructuredLLM
from .plan import load_macro_arc, macro_arc_path, specced_chapters
from .reports import QuarantineLog
from .runner import run_novel

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AUTHORS = REPO_ROOT / "authors"


def _load_dotenv() -> None:
    """
    Read `.env` at the repo root into the environment, without adding a dependency.

    The Anthropic SDK reads ANTHROPIC_API_KEY from the environment and knows nothing about
    files, so without this `.env.example` would be a lie. Never overrides an existing variable:
    an explicit `ANTHROPIC_API_KEY=... storica run` wins over the file.
    """
    path = REPO_ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def _driver(name: str, novel_dir: Path) -> StructuredLLM:
    if name == "replay":
        return ReplayLLM(novel_dir / "06_session")
    if name == "anthropic":
        _load_dotenv()
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise SystemExit(
                "ANTHROPIC_API_KEY is not set. Put it in .env (see .env.example), "
                "or use --driver replay to run without an API key."
            )
        return AnthropicStructuredLLM()
    raise SystemExit(f"unknown driver '{name}' (expected 'replay' or 'anthropic')")


def cmd_new(args: argparse.Namespace) -> int:
    """Create the folder skeleton and the brief. This is the only human-authored artifact."""
    novel_dir = Path(args.novel_dir)
    for sub in ("00_input", "01_canon", "02_plan/chapters", "03_drafts", "04_trace", "05_reports"):
        (novel_dir / sub).mkdir(parents=True, exist_ok=True)

    brief = Brief(
        author_id=args.author,
        spark=args.spark,
        language=args.language,
        chapter_count=args.chapters,
    )
    try:
        path = save_brief(brief, novel_dir / "00_input")
    except FileExistsError:
        print(f"brief already exists at {novel_dir / '00_input' / 'brief.yaml'} — it is immutable")
        return 1

    print(f"created {novel_dir}")
    print(f"edit the brief before running: {path}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    novel_dir = Path(args.novel_dir)
    llm = _driver(args.driver, novel_dir)

    try:
        result = asyncio.run(run_novel(
            novel_dir=novel_dir,
            authors_root=args.authors,
            llm=llm,
            # --no-checkers turns off *both* layers of LLM judgement: the plan-side Intent checker
            # and the prose-side readers. Structure is still enforced; meaning is not.
            checkers=[] if args.no_checkers else None,
            audit=not args.no_audit,
            check_intent=not args.no_checkers,
            max_repairs=args.max_repairs,
            n_candidates=args.prose_candidates,
            samples=args.checker_samples,
        ))
    except ResponseNeeded as pause:
        # Not a failure: the replay driver has run out of recorded answers.
        print(f"\n[paused] {pause}\n")
        return 2
    except MalformedResponse as bad:
        # A recorded answer does not fit its schema. Also not a crash — the answer needs
        # rewriting. Distinct exit code so a driving loop can tell "write a new answer" (2)
        # from "fix the one you wrote" (3) without parsing text.
        print(f"\n[malformed] {bad}\n")
        return 3

    print(f"chapters written: {result.chapters or '(none)'}")
    if result.quarantined:
        print(f"quarantined (excluded from the book): {', '.join(result.quarantined)}")
    if result.novel_path:
        print(f"novel: {result.novel_path}")
    if result.audit_decision:
        print(f"final audit: {result.audit_decision} — {result.audit_summary}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    novel_dir = Path(args.novel_dir)
    canon_file = novel_dir / "01_canon" / "story_model.json"

    print(f"novel: {novel_dir}")
    if not canon_file.exists():
        print("  canon:    not established yet")
        return 0

    canon = load_canon(novel_dir / "01_canon")
    print(f"  canon:    v{canon.version}, {len(canon.characters)} characters, "
          f"{len(canon.motifs)} motifs, {len(canon.promises)} promises")

    if macro_arc_path(novel_dir / "02_plan").exists():
        arc = load_macro_arc(novel_dir / "02_plan")
        specced = specced_chapters(novel_dir / "02_plan")
        drafted = drafted_chapters(novel_dir / "03_drafts")
        print(f"  arc:      {arc.chapter_count} chapters, {len(arc.arc_beats)} beats")
        print(f"  specced:  {specced or '(none)'}")
        print(f"  drafted:  {drafted or '(none)'}")
    else:
        print("  arc:      not planned yet")

    quarantined = QuarantineLog(novel_dir / "05_reports").units()
    if quarantined:
        print(f"  QUARANTINED: {', '.join(quarantined)}")
    if (novel_dir / "novel.md").exists():
        print(f"  novel.md: {(novel_dir / 'novel.md').stat().st_size} bytes")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="storica", description="Canon-centric novel pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    new = sub.add_parser("new", help="create a novel folder and its brief")
    new.add_argument("novel_dir")
    new.add_argument("--author", required=True, help="author id under authors/")
    new.add_argument("--spark", default="", help="the seed thought")
    new.add_argument("--language", default="en")
    new.add_argument("--chapters", type=int, default=None)
    new.set_defaults(func=cmd_new)

    run = sub.add_parser("run", help="run the pipeline (resumable)")
    run.add_argument("novel_dir")
    run.add_argument("--driver", default="replay", choices=["replay", "anthropic"])
    run.add_argument("--authors", default=str(DEFAULT_AUTHORS))
    run.add_argument("--max-repairs", type=int, default=2, dest="max_repairs")
    run.add_argument(
        "--prose-candidates", type=int, default=3, dest="prose_candidates",
        help="drafts to generate per scene before selecting the most alive one (1 = no selection). "
             "Costs N generate calls plus one cheap selection call per scene; set 1 for a cheap run.",
    )
    run.add_argument(
        "--checker-samples", type=int, default=3, dest="checker_samples",
        help="draws per canon-consistency check; blocks only on a majority. 1 disables sampling. "
             "Measured: a single draw flags clean text ~20%% of the time (calibration/FINDINGS.md C4).",
    )
    run.add_argument("--no-audit", action="store_true", help="skip the whole-book final audit")
    run.add_argument("--no-checkers", action="store_true", help="skip LLM checkers (structure only)")
    run.set_defaults(func=cmd_run)

    status = sub.add_parser("status", help="show how far a run has got")
    status.add_argument("novel_dir")
    status.set_defaults(func=cmd_status)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
