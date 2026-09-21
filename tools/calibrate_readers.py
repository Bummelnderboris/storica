"""
Calibrate micro-sense and voice — the two readers that blocked a book without ever being measured.

`calibration/FINDINGS.md` C6 is the standing lesson: vitality's every verdict was defensible and
its *gate* fired on every chapter ever written, and only testing the gate on a matched pair showed
it. Micro-sense and voice had the same shape (binary blocking) and no such test. P6's chapter 1 was
then quarantined by micro-sense on an unglossed date (C7). This harness asks each of them the only
question that matters for a gate — does it block clean prose, and does it block broken prose — on
the same clean control the other calibrations use.

Cases, each drawn k times (`--draws`, default 3), all on v1's chapter 3 as a single scene:

  micro_sense / control   the chapter as written — canon-correct, clean (C3's control)
  micro_sense / planted   the same chapter with four planted breaches of micro-sense AND four
                          invented specifics the invention policy permits (a date, an hour, a
                          street, a file number). The permitted four are the C7 test: a reader
                          that blocks them is recreating the failure that quarantined P6.
  voice       / control   the chapter as written
  voice       / flattened C6's fixture: explained gestures, announced interiority, a closing
                          paragraph that states the meaning — explanatory psychology is a hard
                          "no" on Dürrenmatt's list, so voice must block it

The canon is `novels/der-chrachen/01_canon`, which C1 found carries one corrupted fact (Rutz as a
creditor). Nothing in these fixtures turns on it; it is used only as a slice to judge against.

Usage:
    .venv/bin/python tools/calibrate_readers.py            # run/resume under the replay driver
    .venv/bin/python tools/calibrate_readers.py --report   # score what has been answered
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from storica.authors import load_author  # noqa: E402
from storica.canon import load_canon  # noqa: E402
from storica.checkers import AuthorVoiceChecker, MicroSenseChecker  # noqa: E402
from storica.drivers import ReplayLLM, ResponseNeeded  # noqa: E402
from storica.llm import gather_draws  # noqa: E402
from storica.plan import ChapterSpec, SceneSpec  # noqa: E402
from storica.trace import Tracer  # noqa: E402

V1 = REPO_ROOT / "novels" / "der-chrachen"
OUT = REPO_ROOT / "calibration"
RESULTS = OUT / "results" / "readers"

CONTROL = V1 / "06_prose" / "ch03" / "2_draft.md"
PLANTED = OUT / "fixtures" / "ch03_micro_planted.md"
FLATTENED = OUT / "fixtures" / "ch03_flattened.md"


@dataclass
class Span:
    id: str
    keywords: List[str]


@dataclass
class Case:
    reader: str
    id: str
    path: Path
    must_block: List[Span] = field(default_factory=list)   # planted: a blocking issue should name each
    must_pass: List[Span] = field(default_factory=list)    # permitted: no blocking issue may name any


CASES: List[Case] = [
    Case("micro_sense", "control", CONTROL),
    Case(
        "micro_sense", "planted", PLANTED,
        must_block=[
            Span("named_stranger", ["hürlimann", "gemeindeschreiber", "anton"]),
            Span("impossible_handover", ["flur", "reichte", "zweite seite"]),
            Span("abstraction", ["spannung", "sprachen lange"]),
            Span("self_contradiction", ["nach mittag", "zurückgekehrt", "bis zum abend"]),
        ],
        must_pass=[
            Span("date", ["elfte märz", "elften märz"]),
            Span("hour", ["halb elf"]),
            Span("street", ["postgasse", "laternen"]),
            Span("file_number", ["214"]),
        ],
    ),
    Case("voice", "control", CONTROL),
    Case("voice", "flattened", FLATTENED),
]

READERS = {"micro_sense": MicroSenseChecker, "voice": AuthorVoiceChecker}

SCENE = SceneSpec(
    id="s1",
    location="Amtszimmer, Kirchplatz, Aktenkeller",
    character_ids=["stettler", "feuz", "berta", "rutz"],
    intent="(calibration harness — the chapter judged as one scene)",
    turn="(not specced)",
)


def _spec() -> ChapterSpec:
    """Minimal on purpose, as in `calibrate_checkers.spec_for`: no plan detail v1 never had."""
    return ChapterSpec(
        chapter=3, title="Der Chrachen", purpose="(not specced — calibration harness)",
        pov_character_id="stettler", present_character_ids=SCENE.character_ids,
        advances_beats=[], setups=[], payoffs=[], promises_made=[], promises_kept=[],
        entry_state=[], exit_state=[], scenes=[SCENE],
    )


def _prose(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    # v1 artefacts open with a capture header; the prose starts at the first real paragraph.
    marker = "Der Vormittag war klar"
    return text[text.index(marker):] if marker in text else text


def _result_path(case: Case, draw: int) -> Path:
    return RESULTS / f"{case.reader}.{case.id}.draw{draw}.json"


async def run(draws: int) -> int:
    canon = load_canon(V1 / "01_canon")
    author = load_author("duerrenmatt", REPO_ROOT / "authors")
    llm = ReplayLLM(OUT / "06_session")
    tracer = Tracer(OUT / "04_trace")
    RESULTS.mkdir(parents=True, exist_ok=True)

    async def one(case: Case, draw: int):
        target = _result_path(case, draw)
        if target.exists():
            return None
        checker = READERS[case.reader](llm, tracer=tracer)
        verdict = await checker.check_prose(
            prose=_prose(case.path), canon=canon, spec=_spec(), author=author, scene=SCENE, draw=draw,
        )
        target.write_text(verdict.model_dump_json(indent=2), encoding="utf-8")
        return verdict

    try:
        await gather_draws(one(c, d) for c in CASES for d in range(1, draws + 1))
    except ResponseNeeded:
        print(f"[pending] {len(llm.raised)} call(s) awaiting answers:")
        for r in llm.raised:
            print(f"  - model={r.model} read={r.request_path} write={r.response_path}")
        return 2
    return report(draws)


def _hay(issue: dict) -> str:
    return " ".join([issue.get("unit", ""), issue.get("fix_hint", "")]).lower()


def report(draws: int) -> int:
    rows: List[str] = []
    for case in CASES:
        blocked: List[int] = []
        caught: Dict[str, int] = {s.id: 0 for s in case.must_block}
        wrongly: Dict[str, int] = {s.id: 0 for s in case.must_pass}
        answered = 0
        for d in range(1, draws + 1):
            path = _result_path(case, d)
            if not path.exists():
                continue
            answered += 1
            issues = json.loads(path.read_text(encoding="utf-8")).get("issues", [])
            blocking = [i for i in issues if i.get("severity") == "blocking"]
            blocked.append(len(blocking))
            for s in case.must_block:
                caught[s.id] += any(any(k in _hay(i) for k in s.keywords) for i in blocking)
            for s in case.must_pass:
                wrongly[s.id] += any(any(k in _hay(i) for k in s.keywords) for i in blocking)
        gate = sum(1 for b in blocked if b) if blocked else 0
        rows.append(
            f"{case.reader:<12} {case.id:<10} draws={answered}/{draws}  blocking per draw={blocked}  "
            f"gate fired {gate}/{answered}"
        )
        for sid, n in caught.items():
            rows.append(f"{'':<24} planted  {sid:<20} caught {n}/{answered}")
        for sid, n in wrongly.items():
            rows.append(f"{'':<24} permitted {sid:<19} blocked {n}/{answered}"
                        + ("   <-- C7 recurring" if n else ""))
    print("\n=== Reader calibration: micro-sense and voice ===\n")
    print("\n".join(rows))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draws", type=int, default=3)
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()
    if args.report:
        return report(args.draws)
    return asyncio.run(run(args.draws))


if __name__ == "__main__":
    raise SystemExit(main())
