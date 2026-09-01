"""
Calibrate the Canon-Consistency checker against known-answer data.

The v1 capture is labelled failure data: FINDINGS F6/F9/F12 name exact errors at exact places in
`novels/der-chrachen/06_prose/`. So we do not have to write a new book to find out whether the
checker layer works — we can hand the checker the *correct* canon and the *broken* v1 prose and
score it against an answer key.

Three cases, chosen so the test can fail in both directions:

  ch01_draft     one subtle planted error  (F9: Rutz the priest written as a creditor)
  ch02_revised   five blatant planted errors (F12: the reviser's cascade)
  ch03_draft     CONTROL — written against corrected canon, guardian found 0 contradictions

Without the control the test is worthless: a checker that flags everything scores 100% on planted
errors and is useless in a pipeline, because every chapter would enter a repair loop forever.

## The overfitting arm

`checkers/canon_consistency.py` was written after reading these findings, and its rubric names
this book's failures as examples — "the village priest who acts as a creditor", "she was his widow
AND his housekeeper", "restore the cause of death canon records". Scoring it on der-chrachen alone
would be grading an open-book exam.

So every case runs twice:

  shipped   the rubric as it ships
  generic   the same rubric with every der-chrachen specific replaced by a neutral example

`generic` is the number that predicts performance on the *next* book. If a finding only appears in
the `shipped` arm, the checker did not detect it — it recognised it.

Usage:
    .venv/bin/python tools/calibrate_checkers.py           # run/resume, replay driver
    .venv/bin/python tools/calibrate_checkers.py --report  # score what has been answered so far
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from storica.authors import load_author  # noqa: E402
from storica.canon import load_canon  # noqa: E402
from storica.checkers import canon_consistency as cc  # noqa: E402
from storica.drivers import ReplayLLM, ResponseNeeded  # noqa: E402
from storica.plan import ChapterSpec  # noqa: E402
from storica.trace import Tracer  # noqa: E402

V1 = REPO_ROOT / "novels" / "der-chrachen"
OUT = REPO_ROOT / "calibration"

# --------------------------------------------------------------------------------------------
# The answer key
# --------------------------------------------------------------------------------------------


@dataclass
class PlantedError:
    """One error we know is in the prose, and the words that would show it was found."""

    id: str
    description: str
    # An issue counts as a hit if any of these appears in its unit/canon_ref/fix_hint, lowercased.
    keywords: List[str]
    # True when this exact failure is named in the shipped rubric, so a `shipped`-arm hit is
    # recognition rather than detection.
    named_in_rubric: bool
    # Set when the reference canon turns out to PERMIT what FINDINGS calls an error, which makes
    # this a broken test case rather than a checker miss. Excluded from recall; reported separately.
    canon_permits: str = ""


@dataclass
class Case:
    id: str
    prose_path: Path
    chapter: int
    title: str
    present: List[str]
    planted: List[PlantedError] = field(default_factory=list)
    is_control: bool = False


CASES: List[Case] = [
    Case(
        id="ch01_draft",
        prose_path=V1 / "06_prose" / "ch01" / "2_draft.md",
        chapter=1,
        title="Der Totenschein",
        present=["stettler", "melchior", "rutz", "berta", "marolf"],
        planted=[
            PlantedError(
                id="F9_rutz_creditor",
                description="Rutz, canon's village priest and confessor, is written as a creditor "
                "the dead man owed money to.",
                keywords=["rutz", "pfarrer", "priest", "creditor", "gläubiger", "geld"],
                named_in_rubric=True,
                canon_permits=(
                    "The reference canon records rutz.facts.relation as 'old friend of Stettler; "
                    "Melchior owed him 300 francs privately' AND a relationship rutz creditor_of "
                    "melchior. So the prose calling him a creditor does NOT contradict this canon, "
                    "and both arms were right to let it stand. The canon has absorbed the F11 "
                    "bridging fact — 'priest AND private creditor' — the exact invention FINDINGS "
                    "condemns. Ground truth reconstructed after the fact, by reading corrupted "
                    "prose, inherits the corruption. See calibration/FINDINGS.md."
                ),
            )
        ],
    ),
    Case(
        id="ch02_revised",
        prose_path=V1 / "06_prose" / "ch02" / "4_revised.md",
        chapter=2,
        title="Die Witwe",
        present=["stettler", "berta", "rutz", "feuz", "klara", "melchior"],
        planted=[
            PlantedError(
                id="F12_victim_renamed",
                description="The victim Klara Vogel is renamed 'Anna Vogel, geb. Aebi'.",
                keywords=["klara", "anna", "vogel", "aebi"],
                named_in_rubric=False,
            ),
            PlantedError(
                id="F12_cause_of_death",
                description="Cause of death changes from a fall with no autopsy to poisoning, "
                "with a stomach preparation and an autopsy finding.",
                keywords=["poison", "gift", "sektion", "autopsy", "sturz", "fall", "präparat", "magen"],
                named_in_rubric=True,
            ),
            PlantedError(
                id="F12_stettler_office",
                description="Stettler's office changes from Amtsarzt (physician) to "
                "Amtsstatthalter (magistrate).",
                keywords=["amtsstatthalter", "amtsarzt", "magistrate", "physician", "arzt"],
                named_in_rubric=False,
            ),
            PlantedError(
                id="F12_rutz_split",
                description="Rutz is split into two people: a creditor, plus a separate unnamed priest.",
                keywords=["rutz", "pfarrer", "priest", "creditor", "gläubiger", "zwei"],
                named_in_rubric=True,
            ),
            PlantedError(
                id="F12_berta_role",
                description="Berta, canon's widow of the dead man, is moved into Feuz's home as his "
                "domestic servant.",
                keywords=["berta", "widow", "witwe", "housekeeper", "haushälterin", "magd", "feuz"],
                named_in_rubric=True,
            ),
        ],
    ),
    Case(
        id="ch03_draft",
        prose_path=V1 / "06_prose" / "ch03" / "2_draft.md",
        chapter=3,
        title="Der Chrachen",
        present=["stettler", "berta", "rutz", "marolf", "melchior"],
        planted=[],
        is_control=True,
    ),
]

# --------------------------------------------------------------------------------------------
# The two rubric arms
# --------------------------------------------------------------------------------------------

# Every der-chrachen specific in the shipped rubric, mapped to a neutral example from no book.
# Same instruction, same structure, same specificity — only the worked examples change.
#
# Keys are matched with whitespace-insensitive regex because the rubric is a wrapped string literal
# and these phrases straddle line breaks. An exact-match version of this dict silently rots the
# moment someone re-wraps a paragraph.
GENERICISATIONS: Dict[str, str] = {
    "the village priest who acts as a creditor": "a character who holds one office acting with the authority of another",
    "the widow of the dead man who acts as the protagonist's housekeeper": "a person defined by one relationship behaving as though they stood in a different one",
    '"he is a priest AND a private creditor", "she was his widow AND his housekeeper", "the certificate was signed twice"': '"he holds both offices at once", "she stood in both relations to him", "the document was issued twice"',
    "a doctor who examines like a policeman, a certificate that becomes a confession, a secret the prose treats as public": "a professional who acts outside their competence, a document that changes function, a secret the prose treats as public",
    '"call him Pfarrer, as canon does", "cut the clause claiming she was present", "restore the cause of death canon records"': '"use the office canon gives him", "cut the clause claiming she was present", "restore the fact canon records"',
    # Not der-chrachen-specific, but "creditor" is the exact word F9 turns on: leaving it in the
    # generic arm would still cue the answer.
    "a creditor and debtor who behave as equals": "a superior and a subordinate who behave as equals",
}


def generic_texts() -> tuple[str, str]:
    """
    The shipped (system, rubric) pair with this book's answers removed.

    Both strings have to be treated together: the worked examples are split across them — the
    bridging-fact examples live in the system prompt, the role-drift examples in the rubric — and
    genericising only one arm would leave the answer key half in place.
    """
    system, rubric = cc.SYSTEM, cc.CONSISTENCY_RUBRIC
    for specific, neutral in GENERICISATIONS.items():
        pattern = r"\s+".join(re.escape(word) for word in specific.split())
        replacement = neutral.replace("\\", "\\\\")
        system, in_system = re.subn(pattern, replacement, system, count=1)
        rubric, in_rubric = re.subn(pattern, replacement, rubric, count=1)
        if in_system + in_rubric == 0:
            raise SystemExit(
                "genericisation target found in neither SYSTEM nor CONSISTENCY_RUBRIC — the "
                f"checker changed and this tool is stale. Missing:\n  {specific!r}"
            )
    return system, rubric


ARMS = {
    "shipped": lambda: (cc.SYSTEM, cc.CONSISTENCY_RUBRIC),
    "generic": generic_texts,
}

# --------------------------------------------------------------------------------------------
# Running
# --------------------------------------------------------------------------------------------


def spec_for(case: Case) -> ChapterSpec:
    """
    A deliberately minimal spec.

    Entry/exit state and scenes are left empty on purpose: inventing plan detail the v1 run never
    had would let the checker flag a mismatch against something we made up, which would inflate the
    score with findings that are not about canon at all. This keeps the question narrow — given
    correct canon and this prose, do you find the contradictions?
    """
    return ChapterSpec(
        chapter=case.chapter,
        title=case.title,
        purpose="(not specced — calibration harness)",
        pov_character_id="stettler",
        present_character_ids=case.present,
        advances_beats=[],
        setups=[],
        payoffs=[],
        promises_made=[],
        promises_kept=[],
        entry_state=[],
        exit_state=[],
        scenes=[],
    )


async def run() -> int:
    canon = load_canon(V1 / "01_canon")
    author = load_author("duerrenmatt", REPO_ROOT / "authors")
    llm = ReplayLLM(OUT / "06_session")
    tracer = Tracer(OUT / "04_trace")
    original = (cc.SYSTEM, cc.CONSISTENCY_RUBRIC)
    results_dir = OUT / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    pending = 0
    for case in CASES:
        prose = case.prose_path.read_text(encoding="utf-8")
        for arm, texts in ARMS.items():
            target = results_dir / f"{case.id}.{arm}.json"
            if target.exists():
                continue
            cc.SYSTEM, cc.CONSISTENCY_RUBRIC = texts()  # the only difference between the arms
            try:
                checker = cc.CanonConsistencyChecker(llm, tracer=tracer)
                verdict = await checker.check_prose(
                    prose=prose, canon=canon, spec=spec_for(case), author=author
                )
            except ResponseNeeded as need:
                print(f"[pending] {case.id} / {arm}\n{need}\n")
                pending += 1
                continue
            finally:
                cc.SYSTEM, cc.CONSISTENCY_RUBRIC = original
            target.write_text(verdict.model_dump_json(indent=2), encoding="utf-8")
            print(f"[done] {case.id} / {arm}: {verdict.decision.value}, {len(verdict.issues)} issues")

    if pending:
        print(f"{pending} call(s) awaiting answers — answer them and run again.")
        return 2
    return 0


# --------------------------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------------------------


def _haystack(issue: dict) -> str:
    return " ".join([issue.get("unit", ""), issue.get("canon_ref", ""), issue.get("fix_hint", "")]).lower()


def score() -> int:
    results_dir = OUT / "results"
    rows: List[str] = []
    missing = 0

    for case in CASES:
        for arm in ARMS:
            path = results_dir / f"{case.id}.{arm}.json"
            if not path.exists():
                missing += 1
                continue
            verdict = json.loads(path.read_text(encoding="utf-8"))
            issues = verdict.get("issues", [])
            blocking = [i for i in issues if i.get("severity") == "blocking"]

            if case.is_control:
                verdict_word = "CLEAN" if not blocking else f"{len(blocking)} FALSE POSITIVES"
                rows.append(
                    f"{case.id:<14} {arm:<8} control          {verdict_word}"
                    + (f"  [{verdict.get('decision')}]" if blocking else "")
                )
                for i in blocking:
                    rows.append(f"{'':<14} {'':<8}   false alarm:   {i.get('unit', '')[:60]}")
                continue

            for planted in case.planted:
                hit = any(any(k in _haystack(i) for k in planted.keywords) for i in blocking)
                if planted.canon_permits:
                    rows.append(
                        f"{case.id:<14} {arm:<8} {planted.id:<22} "
                        f"{'INVALID CASE — canon permits it' if not hit else 'flagged anyway (!)'}"
                    )
                    continue
                mark = "CAUGHT" if hit else "MISSED"
                flag = " (named in rubric)" if planted.named_in_rubric and arm == "shipped" else ""
                rows.append(f"{case.id:<14} {arm:<8} {planted.id:<22} {mark}{flag}")
            extra = len(blocking) - sum(
                1
                for i in blocking
                if any(any(k in _haystack(i) for k in p.keywords) for p in case.planted)
            )
            if extra > 0:
                rows.append(f"{'':<14} {arm:<8} {'(unmatched issues)':<22} {extra}")

    print("\n=== Canon-Consistency calibration ===\n")
    print("\n".join(rows) if rows else "(no results yet)")

    valid_total = sum(1 for c in CASES for p in c.planted if not p.canon_permits)
    detect = {}
    for arm in ARMS:
        caught = 0
        for case in CASES:
            path = results_dir / f"{case.id}.{arm}.json"
            if not path.exists() or case.is_control:
                continue
            blocking = [
                i for i in json.loads(path.read_text(encoding="utf-8")).get("issues", [])
                if i.get("severity") == "blocking"
            ]
            caught += sum(
                1 for p in case.planted
                if not p.canon_permits
                and any(any(k in _haystack(i) for k in p.keywords) for i in blocking)
            )
        detect[arm] = (caught, valid_total)

    print("\n--- recall (valid cases only) ---")
    for arm, (caught, total) in detect.items():
        print(f"{arm:<8} {caught}/{total} planted errors caught")
    print(
        "\nThe `generic` row is the one that predicts the next book. A gap between shipped and\n"
        "generic is the checker recognising der-chrachen rather than detecting contradiction."
    )

    invalid = [(c, p) for c in CASES for p in c.planted if p.canon_permits]
    if invalid:
        print("\n--- excluded test cases ---")
        for case, planted in invalid:
            print(f"{case.id} / {planted.id}: {planted.canon_permits}")

    run2 = results_dir / "ch01_draft.shipped.run2.json"
    run1 = results_dir / "ch01_draft.shipped.run1.json"
    if run2.exists() and run1.exists():
        a = json.loads(run1.read_text(encoding="utf-8"))
        b = json.loads(run2.read_text(encoding="utf-8"))
        print(
            "\n--- reliability ---\n"
            f"ch01_draft/shipped answered twice by two fresh agents: "
            f"'{a['decision']}' ({len(a['issues'])} issues) vs '{b['decision']}' ({len(b['issues'])} issues).\n"
            "Same prompt, same model, different gate outcome. n=1 per cell throughout, so treat every\n"
            "number here as a smoke test, not a measurement."
        )
    if missing:
        print(f"\n({missing} result file(s) still unanswered)")
    return 0


# --------------------------------------------------------------------------------------------
# Reliability: the same call, drawn many times
# --------------------------------------------------------------------------------------------
#
# C4 showed one call returning 'revise' with a blocking issue on one draw and 'pass' on another. A
# gate that flips is a gate whose verdict is partly luck, so before choosing a sampling policy we
# need two rates: how often clean text gets flagged (which is what union-blocking amplifies), and
# whether extra draws actually find errors a single draw misses.
#
# The prompt must stay byte-identical across draws — the variance under study is the model's, not
# the prompt's. ReplayLLM keys on a content hash, so identical prompts would replay the same cached
# answer; each draw therefore gets its own session directory instead of a tweaked prompt.

RELIABILITY_CASES = ["ch02_revised", "ch03_draft"]  # the two that decide the policy


async def run_reliability(draws: int) -> int:
    canon = load_canon(V1 / "01_canon")
    author = load_author("duerrenmatt", REPO_ROOT / "authors")
    results_dir = OUT / "results" / "reliability"
    results_dir.mkdir(parents=True, exist_ok=True)
    by_id = {c.id: c for c in CASES}

    pending = 0
    for case_id in RELIABILITY_CASES:
        case = by_id[case_id]
        prose = case.prose_path.read_text(encoding="utf-8")
        for n in range(1, draws + 1):
            target = results_dir / f"{case.id}.draw{n}.json"
            if target.exists():
                continue
            llm = ReplayLLM(OUT / "06_session" / f"draw{n}")  # separate cache, same prompt
            try:
                verdict = await cc.CanonConsistencyChecker(llm, tracer=Tracer(None)).check_prose(
                    prose=prose, canon=canon, spec=spec_for(case), author=author
                )
            except ResponseNeeded as need:
                print(f"[pending] {case.id} draw{n}\n{need}\n")
                pending += 1
                continue
            target.write_text(verdict.model_dump_json(indent=2), encoding="utf-8")
            print(f"[done] {case.id} draw{n}: {verdict.decision.value}, {len(verdict.issues)} issues")

    if pending:
        print(f"{pending} call(s) awaiting answers — answer them and run again.")
        return 2
    return 0


def score_reliability() -> int:
    results_dir = OUT / "results" / "reliability"
    by_id = {c.id: c for c in CASES}
    print("\n=== Reliability: same prompt, independent draws ===\n")

    policy_rows = []
    for case_id in RELIABILITY_CASES:
        case = by_id[case_id]
        draws = sorted(results_dir.glob(f"{case.id}.draw*.json"))
        if not draws:
            continue
        verdicts = [json.loads(p.read_text(encoding="utf-8")) for p in draws]
        blocking_per_draw = [
            [i for i in v.get("issues", []) if i.get("severity") == "blocking"] for v in verdicts
        ]
        n = len(verdicts)
        blocked = sum(1 for b in blocking_per_draw if b)

        label = "CONTROL (clean text)" if case.is_control else "planted errors"
        print(f"{case.id}  [{label}]  n={n}")
        print(f"  decisions:          {[v['decision'] for v in verdicts]}")
        print(f"  blocking per draw:  {[len(b) for b in blocking_per_draw]}")
        print(f"  draws that blocked: {blocked}/{n}")

        if case.is_control:
            # Every block here is a false positive: this chapter is clean.
            p = blocked / n if n else 0.0
            print(f"  ==> false-positive rate per draw: {p:.0%}")
            for k in (1, 3, 5):
                union = 1 - (1 - p) ** k
                print(f"      union-block at k={k}: {union:.0%} chance of blocking clean text")
            policy_rows.append(("fp_per_draw", p))
        else:
            for planted in case.planted:
                if planted.canon_permits:
                    continue
                hits = sum(
                    1 for b in blocking_per_draw
                    if any(any(kw in _haystack(i) for kw in planted.keywords) for i in b)
                )
                print(f"  {planted.id:<22} caught in {hits}/{n} draws")
            union_recall = sum(
                1 for p_ in case.planted if not p_.canon_permits
                and any(any(any(kw in _haystack(i) for kw in p_.keywords) for i in b)
                        for b in blocking_per_draw)
            )
            valid = sum(1 for p_ in case.planted if not p_.canon_permits)
            print(f"  ==> union of all {n} draws catches {union_recall}/{valid} "
                  f"(single draw caught 4/{valid})")
            policy_rows.append(("union_recall", (union_recall, valid)))
        print()

    print("--- reading this ---")
    print(
        "Union-blocking (fire repair if ANY draw raises a blocking issue) is the right rule only if\n"
        "the control's false-positive rate stays low enough that 1-(1-p)^k is tolerable. If clean\n"
        "text blocks often, prefer majority-blocking, or keep k=1 and accept the misses."
    )
    return 0


# --------------------------------------------------------------------------------------------
# Vitality: can it tell alive from flat?
# --------------------------------------------------------------------------------------------
#
# Planted-error scoring cannot work here, because a dull chapter is not *wrong*. So this is a
# discrimination test on a matched pair: the same chapter, same events, same canonical facts, once
# as written and once with the rubric's anti-patterns inserted (explained gestures, announced
# interiority, a closing paragraph that states the meaning).
#
# WHAT THIS CAN AND CANNOT SHOW. The flattened fixture was written by applying the checker's own
# categories, so this is a FLOOR test: if it cannot separate deliberately, blatantly deadened prose
# from the original, it is useless and we know so cheaply. Passing it is weak evidence — it does not
# show the checker can detect the naturally occurring dullness a generator actually produces, which
# is subtler and is not built from a list. Only a human reading a real run can establish that.

VITALITY_PAIR = [
    ("alive", V1 / "06_prose" / "ch03" / "2_draft.md", False),
    ("flattened", OUT / "fixtures" / "ch03_flattened.md", True),
]


async def run_vitality(draws: int) -> int:
    from storica.checkers.vitality import VitalityChecker

    canon = load_canon(V1 / "01_canon")
    author = load_author("duerrenmatt", REPO_ROOT / "authors")
    case = next(c for c in CASES if c.id == "ch03_draft")
    results_dir = OUT / "results" / "vitality"
    results_dir.mkdir(parents=True, exist_ok=True)

    pending = 0
    for label, path, _ in VITALITY_PAIR:
        prose = path.read_text(encoding="utf-8")
        for n in range(1, draws + 1):
            target = results_dir / f"{label}.draw{n}.json"
            if target.exists():
                continue
            llm = ReplayLLM(OUT / "06_session" / f"vitality{n}")
            try:
                verdict = await VitalityChecker(llm, tracer=Tracer(None)).check_prose(
                    prose=prose, canon=canon, spec=spec_for(case), author=author
                )
            except ResponseNeeded as need:
                print(f"[pending] vitality/{label} draw{n}\n{need}\n")
                pending += 1
                continue
            target.write_text(verdict.model_dump_json(indent=2), encoding="utf-8")
            print(f"[done] vitality/{label} draw{n}: {verdict.decision.value}, "
                  f"{len(verdict.issues)} issues")

    if pending:
        print(f"{pending} call(s) awaiting answers — answer them and run again.")
        return 2
    return 0


def score_vitality() -> int:
    results_dir = OUT / "results" / "vitality"
    print("\n=== Vitality: can it tell alive from flat? ===\n")

    from storica.checkers.vitality import VITALITY_BLOCK_PER_1000_WORDS, VITALITY_MIN_BLOCKING

    density = {}
    for label, path, should_block in VITALITY_PAIR:
        paths = sorted(results_dir.glob(f"{label}.draw*.json"))
        if not paths:
            continue
        words = max(len(path.read_text(encoding="utf-8").split()), 1)
        verdicts = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
        counts = [
            len([i for i in v.get("issues", []) if i.get("severity") == "blocking"]) for v in verdicts
        ]
        densities = [c * 1000 / words for c in counts]
        density[label] = densities

        want = "SHOULD block" if should_block else "SHOULD pass"
        print(f"{label:<10} [{want}]  n={len(verdicts)}, {words} words")
        print(f"  raw decisions:      {[v['decision'] for v in verdicts]}  <- binary: no signal")
        print(f"  blocking per draw:  {counts}")
        print(f"  per 1000 words:     {[round(d, 1) for d in densities]}")
        print()

    if len(density) == 2:
        worst_alive, best_flat = max(density["alive"]), min(density["flattened"])
        print(f"separation: alive tops out at {worst_alive:.1f}/1000, "
              f"flattened bottoms out at {best_flat:.1f}/1000")
        print(f"gate: block at >= {VITALITY_BLOCK_PER_1000_WORDS}/1000 "
              f"and >= {VITALITY_MIN_BLOCKING} issues")

        if best_flat <= worst_alive:
            print("VERDICT: the populations overlap. Density cannot gate this either.")
        elif not (worst_alive < VITALITY_BLOCK_PER_1000_WORDS <= best_flat):
            print("VERDICT: separated, but the configured threshold does not sit between them.")
        else:
            print("VERDICT: the SIGNAL discriminates cleanly and the threshold sits between the")
            print("         populations. The BINARY (any issue = block) does not discriminate at")
            print("         all — both sides block 3/3 — which is why the gate is density-based.")
    print(
        "\nFloor test only: the flattened fixture was built from the checker's own rubric, so a pass\n"
        "is weak evidence. A failure would have been decisive."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--vitality", type=int, metavar="N", default=0,
        help="discrimination test: N draws on a matched alive/flattened pair",
    )
    parser.add_argument("--report", action="store_true", help="score existing results only")
    parser.add_argument(
        "--reliability", type=int, metavar="N", default=0,
        help="draw the same call N times per case to measure the flip rate",
    )
    args = parser.parse_args()

    if args.vitality:
        code = asyncio.run(run_vitality(args.vitality))
        if code == 0:
            score_vitality()
        return code
    if args.reliability:
        code = asyncio.run(run_reliability(args.reliability))
        if code == 0:
            score_reliability()
        return code
    if args.report:
        score()
        if (OUT / "results" / "reliability").exists():
            score_reliability()
        return 0
    code = asyncio.run(run())
    if code == 0:
        score()
    return code


if __name__ == "__main__":
    sys.exit(main())
