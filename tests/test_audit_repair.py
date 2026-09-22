"""
Tests for acting on the final audit (`src/storica/audit_repair.py`).

Run from the repo root:
    .venv/bin/python -m pytest tests/ -q

P6's first complete book ended with the final auditor returning `revise` on eight cross-chapter
contradictions, and nothing in the pipeline could act on them. Under test: each blocking finding is
routed to exactly one chapter, repaired there under the ordinary contract, verified against the
finding, and the book is audited again — bounded, resumable, and never by rewriting a chapter that
already passed its gate.
"""

from __future__ import annotations

import asyncio
import json

from storica.audit_repair import repair_from_audit, route
from storica.canon import Severity
from storica.checkers import Decision, RepairCheck, Verdict
from storica.checkers.base import CheckerIssue
from storica.checkers.verifier import IssueResolution
from storica.llm import FakeStructuredLLM
from storica.runner import run_novel

from test_runner import (  # noqa: E402 — the one-chapter planned novel and its fixtures
    AUTHORS_ROOT,
    _canon,
    _extraction,
    _spec,
    planned,  # noqa: F401 — pytest fixture
)


def _finding(unit: str, fix_hint: str = "align the detail with the earlier chapter") -> CheckerIssue:
    return CheckerIssue(unit=unit, kind="coherence", severity=Severity.BLOCKING,
                        canon_ref="", fix_hint=fix_hint)


def _audit(decision=Decision.REVISE, issues=()) -> Verdict:
    return Verdict(decision=decision, summary="audited", issues=list(issues), conflict="")


def _resolved(n: int = 1) -> RepairCheck:
    return RepairCheck(
        resolutions=[IssueResolution(index=i + 1, resolved=True, note="n") for i in range(n)],
        introduced=[],
    )


# --------------------------------------------------------------------------------------------
# Routing: exactly one side of a contradiction moves
# --------------------------------------------------------------------------------------------

def test_a_contradiction_between_two_chapters_is_repaired_in_the_later_one():
    """The earlier chapter was reconciled into canon first; the later one drifted from it."""
    assert route(_finding("ch01 vs ch03"), [1, 2, 3]) == 3


def test_a_fix_hint_that_names_one_chapter_decides():
    finding = _finding("ch01 vs ch03", fix_hint="In ch01, change the hour to match")
    assert route(finding, [1, 2, 3]) == 1


def test_a_single_chapter_finding_stays_there_and_an_unknown_one_is_unrouted():
    assert route(_finding("ch02"), [1, 2, 3]) == 2
    assert route(_finding("novel"), [1, 2, 3]) is None
    assert route(_finding("ch07"), [1, 2, 3]) is None


# --------------------------------------------------------------------------------------------
# One round of repair
# --------------------------------------------------------------------------------------------

_LONG = "Ein Absatz, der lang genug ist, um nicht als Stummel zu gelten. " * 4
BEFORE = f"# Titel\n\n{_LONG}\n\nDer Hund bellte um neun.\n\n{_LONG}"
AFTER = f"# Titel\n\n{_LONG}\n\nDer Hund bellte um zehn.\n\n{_LONG}"


def _run_repair(llm, drafts, findings, **kw):
    return asyncio.run(repair_from_audit(
        verdict=_audit(issues=findings), drafts=drafts, specs={1: _spec(), 2: _spec()},
        canon=_canon(), llm=llm, **kw,
    ))


def test_a_routed_finding_is_repaired_and_verified():
    llm = FakeStructuredLLM(texts=[AFTER], responses=[_resolved()])
    result = _run_repair(llm, {1: BEFORE}, [_finding("ch01")])

    assert result.texts == {1: AFTER}
    assert result.unresolved == []
    assert "ch01: align the detail" in llm.calls[0].prompt     # the finding reaches the repairer


def test_a_rewrite_is_rejected_and_the_gated_chapter_kept():
    rewrite = "# Anders\n\nGanz neu.\n\nAuch neu.\n\n" + "Völlig neu, und lang genug. " * 20
    llm = FakeStructuredLLM(texts=[rewrite, rewrite])
    result = _run_repair(llm, {1: BEFORE}, [_finding("ch01")], max_repairs=2)

    assert result.texts == {}                                   # nothing unread enters the book
    assert len(result.unresolved) == 1


def test_an_unrouted_finding_is_recorded_not_guessed():
    llm = FakeStructuredLLM()
    result = _run_repair(llm, {1: BEFORE}, [_finding("novel")])
    assert result.texts == {} and llm.calls == []
    assert result.unrouted == ["novel: align the detail with the earlier chapter"]


# --------------------------------------------------------------------------------------------
# The run loop: audit, repair, audit again
# --------------------------------------------------------------------------------------------

SCENE = "Erster Absatz der Szene, lang genug um kein Stummel zu sein, " * 3 + \
        "\n\nDer Hund bellte um neun, und niemand stand auf.\n\n" + \
        "Letzter Absatz der Szene, ebenfalls lang genug um zu zählen. " * 3


def test_a_revise_from_the_audit_is_repaired_and_the_book_audited_again(planned):
    fixed = SCENE.replace("um neun", "um zehn")
    llm = FakeStructuredLLM(
        texts=[SCENE, "# Das Protokoll\n\n" + fixed],
        responses=[
            _extraction(),
            _audit(issues=[_finding("ch01", "make the hour ten, as canon says")]),
            _resolved(),
            _audit(Decision.PASS),
        ],
    )

    result = asyncio.run(run_novel(novel_dir=planned, authors_root=AUTHORS_ROOT, llm=llm,
                                   checkers=[]))

    assert result.audit_decision == "pass" and result.is_done
    assert "um zehn" in (planned / "03_drafts" / "ch01.md").read_text()
    assert "um zehn" in (planned / "novel.md").read_text()
    state = json.loads((planned / "05_reports" / "state.json").read_text())
    assert state["audit_rounds"] == 1


def test_audit_repairs_zero_reports_and_stops(planned):
    llm = FakeStructuredLLM(
        texts=[SCENE],
        responses=[_extraction(), _audit(issues=[_finding("ch01")])],
    )

    result = asyncio.run(run_novel(novel_dir=planned, authors_root=AUTHORS_ROOT, llm=llm,
                                   checkers=[], audit_repairs=0))

    assert result.audit_decision == "revise" and not result.is_done
    assert "um neun" in (planned / "03_drafts" / "ch01.md").read_text()
