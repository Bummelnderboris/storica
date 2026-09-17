"""
Stage 4 — Chapter spec, elaborated just-in-time (DESIGN §5, §7).

Reads: the full canon + the macro arc (+ the previous chapter's exit state).
Writes: `02_plan/chapters/chNN.spec.json`.

Just-in-time is the point (principle 2): we never write a paragraph-level outline of a whole novel
up front, because that outline is itself novel-length and drifts. Chapter N is elaborated from
validated canon when chapter N is needed — so it inherits every fact reconciled since chapter 1.

This is also the down-leg of the macro→micro seam (§7): the spec names, by id, the beats to
advance, the setups to plant and payoffs to deliver, and the entry/exit state — and the prose call
in P4 is generated from that plus the full canon slice, never from a truncated blueprint (F5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from ..authors import AuthorModel
from ..canon import Issue, Severity, StoryModel, blocking, canon_slice
from ..checkers import Escalation, IntentChecker
from ..checkers.base import Decision
from ..llm import StructuredLLM, stage_model
from ..plan import ChapterSpec, MacroArc, validate_chapter_spec, validate_continuity
from ..trace import Tracer
from .gate import GateFailed, format_issues, run_gated

SYSTEM = """You are the Chapter-spec agent of an autonomous novel pipeline.

You elaborate ONE chapter from validated canon and the macro arc, just before it is written. You do
not write prose. You produce a specification: purpose, POV, cast, the beats this chapter must
deliver, the motifs and promises it must plant or pay off, the canonical state at its open and
close, and its scenes.

Everything is referenced by canon ID. You carry exactly the assignment the arc gave this chapter —
no more (do not steal a later chapter's beat) and no less (do not drop one you were given)."""


class ChapterSpecGateFailed(GateFailed):
    """The chapter spec still had blocking issues when the repair budget ran out."""


@dataclass
class ChapterSpecResult:
    spec: ChapterSpec
    issues: List[Issue] = field(default_factory=list)
    repairs: int = 0

    @property
    def is_valid(self) -> bool:
        return not blocking(self.issues)


def chapter_assignment_block(chapter: int, canon: StoryModel, arc: MacroArc, previous: Optional[ChapterSpec]) -> str:
    """Exactly what the macro arc requires of this chapter. The spec must match it, item for item."""
    act = arc.act_for(chapter)
    tension = next((t for t in arc.tension_curve if t.chapter == chapter), None)
    turns = [tp for tp in arc.turning_points if tp.chapter == chapter]

    beats = "\n".join(
        f"- [{b.id}] {b.character_id}: {b.beat}  (advances: {b.advances})" for b in arc.beats_for(chapter)
    ) or "- (none)"
    setups = "\n".join(
        f"- [{m.id}] plant: {m.desc}" for m in canon.motifs if m.setup_ch == chapter
    ) or "- (none)"
    payoffs = "\n".join(
        f"- [{m.id}] deliver: {m.desc}" for m in canon.motifs if m.payoff_ch == chapter
    ) or "- (none)"
    made = "\n".join(
        f"- [{p.id}] make: {p.desc}" for p in canon.promises if p.made_ch == chapter
    ) or "- (none)"
    kept = "\n".join(
        f"- [{p.id}] keep: {p.desc}" for p in canon.promises if p.kept_ch == chapter
    ) or "- (none)"
    turning = "\n".join(f"- [{tp.id}] {tp.description} (reverses: {tp.reverses})" for tp in turns) or "- (none)"
    entry = "\n".join(f"- {s.key}: {s.value}" for s in previous.exit_state) if previous else "- (this is the first chapter)"

    return f"""# The assignment for chapter {chapter} (from the macro arc — carry ALL of it, and nothing else)

Book shape: {arc.shape}
Act: {act.number if act else '?'} — {act.purpose if act else '(none)'}
Intended tension: {tension.tension if tension else '?'} ({tension.note if tension else ''})

## Arc beats this chapter MUST deliver
{beats}

## Turning points landing here
{turning}

## Motifs to set up
{setups}

## Motifs to pay off
{payoffs}

## Promises to make
{made}

## Promises to keep
{kept}

## State this chapter opens from (previous chapter's exit state)
{entry}"""


def _ruling_block(guidance: str) -> str:
    """
    A binding ruling, carried into a re-attempt.

    Empty guidance must leave the prompt **byte-identical** to the un-adjudicated one: the replay
    driver keys its cache on the exact prompt, so a stray newline here would orphan every answer a
    part-finished run has already recorded.
    """
    if not guidance.strip():
        return ""
    return (
        "\n\n# Binding ruling (already adjudicated against immutable ground truth — obey, do not "
        f"re-open)\n{guidance}"
    )


def _draft_prompt(
    chapter: int,
    canon: StoryModel,
    arc: MacroArc,
    author: AuthorModel,
    previous: Optional[ChapterSpec],
    guidance: str = "",
) -> str:
    return f"""{canon_slice(canon)}

{author.voice_block()}

{chapter_assignment_block(chapter, canon, arc, previous)}{_ruling_block(guidance)}

## Task
Write the specification for chapter {chapter}.

Rules (checked mechanically — violations fail the stage):
- `advances_beats` lists exactly the beat ids scheduled for this chapter, all of them.
- `setups`/`payoffs`/`promises_made`/`promises_kept` list exactly the ledger ids scheduled here.
- `pov_character_id` and every scene's cast are canon ids drawn from `present_character_ids`.
- `entry_state` carries forward the previous chapter's exit state (changing a value is fine —
  dropping the key silently is not).
- Every scene has an intent and a turn.

Rules (checked by a fresh Intent checker):
- The purpose says what is different about the story after this chapter. "Builds tension" is not
  a purpose.
- Every assigned beat must be deliverable by a named scene — say which scene carries it in that
  scene's intent.
- Every scene turns: something is true at its end that was not true at its start. Cut scenes that
  only convey information.
- Everyone present does something. A character in the room to be described is not present.
- Nothing may contradict the canon slice above."""


def _repair_prompt(spec: ChapterSpec, issues: List[Issue]) -> str:
    return f"""The chapter spec you produced failed review.

## Issues to fix
{format_issues(issues)}

## Your current spec
{spec.model_dump_json(indent=2)}

## Task
Emit the CORRECTED full spec for the same chapter.

- Fix exactly what the issues name; keep the ids and scenes that were fine.
- If an issue says a beat is dropped, add the scene that carries it. If it says a beat is
  misplaced, remove it — it belongs to another chapter.
- If a scene does not turn, either give it a real turn or cut it. Do not restate its intent."""


async def build_chapter_spec(
    *,
    chapter: int,
    canon: StoryModel,
    arc: MacroArc,
    author: AuthorModel,
    llm: StructuredLLM,
    previous_spec: Optional[ChapterSpec] = None,
    tracer: Optional[Tracer] = None,
    intent_checker: Optional[IntentChecker] = None,
    model: str = stage_model("chapter_spec"),
    max_repairs: int = 2,
    strict: bool = True,
    max_tokens: int = 16000,
    guidance: str = "",
) -> ChapterSpecResult:
    """Elaborate one chapter spec from canon + arc, gated and repaired."""
    tracer = tracer or Tracer(None)

    async def evaluate(spec: ChapterSpec) -> List[Issue]:
        issues = validate_chapter_spec(spec, canon, arc)
        issues += validate_continuity(spec, previous_spec)
        if spec.chapter != chapter:
            issues.append(Issue(
                "spec.wrong_chapter", Severity.BLOCKING,
                f"spec is for chapter {spec.chapter}, not {chapter}", f"ch{chapter:02d}"))
        if blocking(issues) or intent_checker is None:
            return issues
        verdict = await intent_checker.check_chapter_spec(
            spec, canon, arc, author_block=author.voice_block()
        )
        if verdict.decision == Decision.ESCALATE:
            raise Escalation(f"ch{chapter:02d}_spec", verdict.conflict, verdict)
        return issues + verdict.to_issues("intent")

    outcome = await run_gated(
        llm=llm,
        schema=ChapterSpec,
        system=SYSTEM,
        prompt=_draft_prompt(chapter, canon, arc, author, previous_spec, guidance),
        repair_prompt=_repair_prompt,
        evaluate=evaluate,
        stage=f"ch{chapter:02d}_spec",
        model=model,
        max_tokens=max_tokens,
        tracer=tracer,
        max_repairs=max_repairs,
        strict=strict,
        failure=ChapterSpecGateFailed,
    )

    spec: ChapterSpec = outcome.draft  # type: ignore[assignment]
    return ChapterSpecResult(spec=spec, issues=outcome.issues, repairs=outcome.repairs)
