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
    storica develop novels/der-chrachen-v3 pitch --note "B, aber der Arzt ist jünger"
    storica map    novels/der-chrachen-v2
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from .brief import Brief, save_brief
from .canon import load_canon
from .drafts import drafted_chapters
from .drivers import MalformedResponse, ReplayLLM, ResponseNeeded
from .llm import AnthropicStructuredLLM, LLMRefusal, StructuredLLM
from .plan import load_macro_arc, macro_arc_path, specced_chapters
from .reports import QuarantineLog
from .runner import run_novel
from .stages import GateFailed

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AUTHORS = REPO_ROOT / "authors"


def _load_dotenv() -> None:
    """
    Read `.env` at the repo root into the environment, without adding a dependency.

    The Anthropic SDK reads ANTHROPIC_API_KEY from the environment and knows nothing about
    files, so without this `.env.example` would be a lie. Never overrides an existing variable:
    an explicit `ANTHROPIC_API_KEY=... storica run` wins over the file.

    An empty assignment (`ANTHROPIC_API_KEY=`, which is what `.env.example` is copied to) is
    skipped rather than exported as "". The SDK resolves credentials in order and an empty
    variable still *wins* that resolution — so loading it would shadow a key the user had
    supplied another way, and produce an auth error that points at the wrong thing.
    """
    path = REPO_ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip("'\"")
        if value:
            os.environ.setdefault(key.strip(), value)


def _driver(name: str, novel_dir: Path, session_dir: str = "06_session") -> StructuredLLM:
    if name == "replay":
        return ReplayLLM(novel_dir / session_dir)
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
    """
    Create the novel folder with its brief, the only human-authored artifact.

    Only `00_input/` is made. Every stage creates its own folder when it first writes, so empty
    `01_canon/`, `04_trace/` and the rest would only be noise, and a writers'-room novel never
    uses them at all.
    """
    novel_dir = Path(args.novel_dir)

    brief = Brief(
        author_id=args.author,
        spark=args.spark,
        thoughts=args.thoughts,
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


def _report_pause(pause: ResponseNeeded, llm: StructuredLLM) -> int:
    """
    A replay driver ran out of recorded answers. List every call this run is waiting on, one per
    line, so a driver can answer them in parallel. Model and paths only — never the prompt (see the
    write-novel skill).
    """
    print(f"\n[paused] {pause}\n")
    raised = getattr(llm, "raised", [])
    if raised:
        print(f"[pending] {len(raised)} call(s) awaiting an answer in this run:")
        for r in raised:
            print(f"  - model={r.model} read={r.request_path} write={r.response_path}")
        print()
    return 2


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
            retry_quarantined=args.retry_quarantined,
            audit_repairs=args.audit_repairs,
        ))
    except ResponseNeeded as pause:
        # Not a failure: the replay driver has run out of recorded answers.
        return _report_pause(pause, llm)
    except MalformedResponse as bad:
        # A recorded answer does not fit its schema. Also not a crash — the answer needs
        # rewriting. Distinct exit code so a driving loop can tell "write a new answer" (2)
        # from "fix the one you wrote" (3) without parsing text.
        print(f"\n[malformed] {bad}\n")
        return 3
    except GateFailed as failed:
        # Canon or the macro arc could not pass its gate. There is no chapter to quarantine at
        # that point, so the run stops — with the issues, not a traceback.
        print(f"\n[failed] a stage could not pass its gate within the repair budget:\n{failed}\n")
        return 1
    except LLMRefusal as refusal:
        print(f"\n[refused] the model declined a call: {refusal}\n")
        return 1

    print(f"chapters written: {result.chapters or '(none)'}")
    if result.quarantined:
        print(f"quarantined (excluded from the book): {', '.join(result.quarantined)}")
    if result.novel_path:
        print(f"novel: {result.novel_path}")
    if result.audit_decision:
        print(f"final audit: {result.audit_decision} — {result.audit_summary}")
    if llm.usage.calls:
        print(f"cost: {llm.usage.summary()}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    novel_dir = Path(args.novel_dir)
    canon_file = novel_dir / "01_canon" / "story_model.json"

    print(f"novel: {novel_dir}")

    if not canon_file.exists():
        print("  canon:    not established yet")
    else:
        canon = load_canon(novel_dir / "01_canon")
        print(f"  canon:    v{canon.version}, {len(canon.characters)} characters, "
              f"{len(canon.motifs)} motifs, {len(canon.promises)} promises")

        if macro_arc_path(novel_dir / "02_plan").exists():
            arc = load_macro_arc(novel_dir / "02_plan")
            print(f"  arc:      {arc.chapter_count} chapters, {len(arc.arc_beats)} beats")
            print(f"  specced:  {specced_chapters(novel_dir / '02_plan') or '(none)'}")
            print(f"  drafted:  {drafted_chapters(novel_dir / '03_drafts') or '(none)'}")
        else:
            print("  arc:      not planned yet")

        if (novel_dir / "novel.md").exists():
            print(f"  novel.md: {(novel_dir / 'novel.md').stat().st_size} bytes")

    # Reported unconditionally, and last. These are the two things a person most needs to see —
    # what was dropped, and what it cost — so neither may hide behind an earlier "nothing yet".
    # `status` is read-only: it must not create `05_reports/` for a path that has no novel.
    reports_dir = novel_dir / "05_reports"
    quarantined = QuarantineLog(reports_dir).units() if reports_dir.is_dir() else []
    if quarantined:
        print(f"  QUARANTINED: {', '.join(quarantined)}")

    report = reports_dir / "run_report.json"
    if report.exists():
        try:
            usage = json.loads(report.read_text(encoding="utf-8")).get("usage") or {}
            calls = int(usage.get("calls") or 0)
            cost = float(usage.get("estimated_cost_usd") or 0)
        except (ValueError, TypeError, AttributeError) as bad:
            print(f"  last run: run_report.json is unreadable ({bad})")
        else:
            if calls:
                print(f"  last run: {calls} calls, ~${cost:.2f}")
    return 0


def cmd_develop(args: argparse.Namespace) -> int:
    """The writers' room: one step, one round. See `room/steps.py` and the /develop skill."""
    from . import room
    from .authors import load_author
    from .brief import load_brief
    from .room.steps import SESSION_DIR

    novel_dir = Path(args.novel_dir)
    try:
        brief = load_brief(novel_dir / "00_input")
    except FileNotFoundError:
        print(f"no brief at {novel_dir / '00_input' / 'brief.yaml'} — create one with `storica new`", file=sys.stderr)
        return 1

    if not args.step:
        print(f"{novel_dir}")
        for line in room.overview(novel_dir, brief.language):
            print(f"  {line}")
        print("  (characters, storyline, scene cards and chapters come in later rework phases)")
        return 0

    try:
        room.step(args.step)
        if args.note:
            room.add_note(novel_dir, args.step, brief.language, args.note)
            print(f"note added to {room.step(args.step).filename}")
        if args.approve:
            doc = room.approve(novel_dir, args.step, brief.language)
            print(f"approved: {room.step(args.step).filename} v{doc.version}")
            return 0
    except (KeyError, ValueError) as bad:
        print(f"[refused] {bad.args[0]}", file=sys.stderr)
        return 1

    llm = _driver(args.driver, novel_dir, SESSION_DIR)
    try:
        outcome = asyncio.run(room.advance(
            novel_dir=novel_dir, step_id=args.step, brief=brief,
            author=load_author(brief.author_id, args.authors), llm=llm,
        ))
    except ResponseNeeded as pause:
        return _report_pause(pause, llm)
    except MalformedResponse as bad:
        print(f"\n[malformed] {bad}\n")
        return 3
    except LLMRefusal as refusal:
        print(f"\n[refused] the model declined a call: {refusal}\n")
        return 1
    print(outcome.message)
    print(f"document: {outcome.path}")
    return 0


def cmd_map(args) -> int:
    from .agent_map import has_trace, write_map

    novel_dir = Path(args.novel_dir) if args.novel_dir else None
    if novel_dir is not None and not has_trace(novel_dir):
        print(f"no run to map: {novel_dir} has no 04_trace/ or _trace/", file=sys.stderr)
        return 1
    default = novel_dir / "05_reports" / "agent_map.html" if novel_dir else Path("agent_map.html")
    out = write_map(Path(args.out) if args.out else default, novel_dir)
    print(f"agent map: {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="storica", description="Canon-centric novel pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    new = sub.add_parser("new", help="create a novel folder and its brief")
    new.add_argument("novel_dir")
    new.add_argument("--author", required=True, help="author id under authors/")
    new.add_argument("--spark", default="", help="the seed thought")
    new.add_argument("--thoughts", default="", help="anything else the creator said about the book, verbatim")
    new.add_argument("--language", default="en")
    new.add_argument("--chapters", type=int, default=None)
    new.set_defaults(func=cmd_new)

    run = sub.add_parser("run", help="run the pipeline (resumable)")
    run.add_argument("novel_dir")
    run.add_argument("--driver", default="replay", choices=["replay", "anthropic"])
    run.add_argument("--authors", default=str(DEFAULT_AUTHORS))
    run.add_argument(
        "--max-repairs", type=int, default=3, dest="max_repairs",
        help="repair rounds per unit. Each round is one repair plus one verification call against "
             "the pinned issues, so the budget converges rather than re-rolling (FINDINGS C7).",
    )
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
    run.add_argument(
        "--retry-quarantined", action="store_true", dest="retry_quarantined",
        help="release every quarantined chapter and attempt it again (combine with a larger "
             "--max-repairs). The original quarantine record is kept; a release is appended.",
    )
    run.add_argument("--no-audit", action="store_true", help="skip the whole-book final audit")
    run.add_argument(
        "--audit-repairs", type=int, default=2, dest="audit_repairs",
        help="rounds of acting on a 'revise' from the final audit: its blocking findings are routed "
             "to chapters, repaired and verified, and the book is audited again. 0 = report only.",
    )
    run.add_argument("--no-checkers", action="store_true", help="skip LLM checkers (structure only)")
    run.set_defaults(func=cmd_run)

    status = sub.add_parser("status", help="show how far a run has got")
    status.add_argument("novel_dir")
    status.set_defaults(func=cmd_status)

    dev = sub.add_parser(
        "develop", help="the writers' room: develop the novel with the creator, one step at a time",
    )
    dev.add_argument("novel_dir")
    dev.add_argument("step", nargs="?", default=None, help="the step to advance (e.g. pitch); omit for an overview")
    dev.add_argument("--note", default=None, help="the creator's words, added verbatim to the step's notes before the round")
    dev.add_argument("--approve", action="store_true", help="approve the step's current document")
    dev.add_argument("--driver", default="replay", choices=["replay", "anthropic"])
    dev.add_argument("--authors", default=str(DEFAULT_AUTHORS))
    dev.set_defaults(func=cmd_develop)

    amap = sub.add_parser(
        "map", help="draw the agents and their instructions as an HTML page; with a novel, add every call it made",
    )
    amap.add_argument("novel_dir", nargs="?", default=None)
    amap.add_argument("--out", default=None, help="where to write the page (default: <novel>/05_reports/agent_map.html, or ./agent_map.html)")
    amap.set_defaults(func=cmd_map)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
