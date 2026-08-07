"""
Stage 5 — Grounded prose (DESIGN §5, §6, §7).

Reads: one `ChapterSpec` + the **full canon slice** for everything each scene touches.
Writes: the chapter as markdown (the caller persists it to `03_drafts/chNN.md`).

Three v1 failures shape this module, and each one is a rule here rather than a hope:

- **F5 — truncated context.** v1 threaded `raw_blueprint[:800]` into the writer, so a chapter barely
  knew what the previous one decided. Here every scene call carries `canon_slice(...)` for exactly
  the characters, motifs and promises that scene touches: the complete canonical truth about what
  it handles, never a prefix of a summary.
- **F9 — canon drift the critic could not see.** v1's writer recast the priest as a creditor and
  nothing caught it. Here the canon slice is in the prompt as *source of truth*, the writer is
  forbidden from inventing facts, and every checker judging the scene is handed the same slice.
- **F8 — averaging.** Checkers run on the **scene**, not on the chapter, so one hollow scene cannot
  be averaged away by four good ones — and they run again on the assembled chapter, because some
  failures (a repeated image, a turn that lands twice) only exist at chapter scale.

The macro→micro seam (§7) is carried explicitly: the beats to advance and the setups/payoffs to
deliver are named **by id in the prompt**. Intent is stated, never implied — an agent that is only
*hinted* at what a scene is for will write something fluent that is for nothing.

Prose is not schema-shaped, so it cannot use `run_gated`; this module hand-writes the same loop and
keeps its properties: cheap deterministic checks before expensive LLM ones, a bounded repair budget
per unit, and a raise rather than a broken unit passed downstream.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict, Field
from typing import Awaitable, Callable, List, Optional, Sequence, Tuple

from ..authors import AuthorModel
from ..canon import Issue, Severity, StoryModel, blocking, canon_slice
from ..checkers.base import Decision, Escalation
from ..checkers.prose_base import ProseChecker
from ..llm import StructuredLLM
from ..plan import ChapterSpec, MacroArc, SceneSpec
from ..trace import Tracer
from .gate import GateFailed, format_issues

SCENE_DIVIDER = "* * *"

# How much of the preceding prose rides into the next call. Enough to inherit rhythm, sentence
# length and the temperature of the last image — not so much that the model starts continuing a
# paragraph instead of opening a scene.
TAIL_CHARS = 800

# Below this, a "scene" is a stub or an apology, and no amount of LLM judgement is needed to know
# it. Deterministic, so it costs nothing to catch (the F3 cost reclaim).
MIN_SCENE_CHARS = 400

_LANGUAGE_NAMES = {
    "de": "German (Deutsch)",
    "en": "English",
    "fr": "French (français)",
    "it": "Italian (italiano)",
    "es": "Spanish (español)",
}


class ProseGateFailed(GateFailed):
    """A prose unit still had blocking issues when its repair budget ran out."""


@dataclass
class ProseResult:
    chapter: int
    text: str
    scenes: List[str] = field(default_factory=list)
    issues: List[Issue] = field(default_factory=list)
    repairs: int = 0

    @property
    def is_valid(self) -> bool:
        return not blocking(self.issues)


SYSTEM = """You are the Prose agent of an autonomous novel pipeline.

You write ONE unit of prose at a time, in the novel's language, in the voice of the given author.

The canon slice you are handed is the source of truth. It wins over anything you would prefer to be
the case, over anything that would be more dramatic, and over anything you half-remember from
earlier. You may invent texture — weather, gesture, the grain of a table, what the room smells like.
You may never invent a fact about a person, a place, a time, or an event. If the unit cannot be
written without a fact you were not given, write around it. Do not supply it.

Write the prose and nothing else: no headings, no scene labels, no dividers, no notes on what you
did or why."""


def _language(canon: StoryModel) -> str:
    code = (canon.constraints.language or "en").strip()
    return _LANGUAGE_NAMES.get(code.lower(), code)


def _tail(text: str, chars: int = TAIL_CHARS) -> str:
    return text.strip()[-chars:]


def _scene_slice(spec: ChapterSpec, canon: StoryModel, scene: SceneSpec) -> str:
    return canon_slice(
        canon,
        character_ids=scene.character_ids,
        motif_ids=[*spec.setups, *spec.payoffs],
        promise_ids=[*spec.promises_made, *spec.promises_kept],
    )


def _chapter_slice(spec: ChapterSpec, canon: StoryModel) -> str:
    return canon_slice(
        canon,
        character_ids=spec.present_character_ids,
        motif_ids=[*spec.setups, *spec.payoffs],
        promise_ids=[*spec.promises_made, *spec.promises_kept],
    )


def _ledger_block(spec: ChapterSpec, canon: StoryModel) -> str:
    """The chapter's ledger duties, by id. Empty lines are omitted so the prompt stays readable."""
    def rows(ids: List[str], items, verb: str) -> List[str]:
        by_id = {i.id: i for i in items}
        return [f"- {verb} [{i}] {by_id[i].desc if i in by_id else '(not in canon)'}" for i in ids]

    lines = (
        rows(spec.setups, canon.motifs, "plant motif")
        + rows(spec.payoffs, canon.motifs, "pay off motif")
        + rows(spec.promises_made, canon.promises, "make promise")
        + rows(spec.promises_kept, canon.promises, "keep promise")
    )
    return "\n".join(lines) or "- (nothing scheduled for this chapter)"


def scene_assignment_block(spec: ChapterSpec, arc: MacroArc, canon: StoryModel, scene: SceneSpec) -> str:
    """
    What the macro arc requires of *this scene*, by id (DESIGN §7, down-leg).

    Beats are assigned to a scene by their character: a beat belongs to the scene where the person
    it happens to is present. Beats for this chapter whose character is elsewhere are still listed,
    marked as another scene's job, so this scene neither drops them nor steals them.
    """
    cast = set(scene.character_ids)
    beats = arc.beats_for(spec.chapter)
    mine = [b for b in beats if b.character_id in cast]
    elsewhere = [b for b in beats if b.character_id not in cast]

    mine_lines = "\n".join(
        f"- [{b.id}] {b.character_id}: {b.beat}  (advances their {b.advances})" for b in mine
    ) or "- (none — this scene carries the chapter forward without a scheduled beat)"
    other_lines = "\n".join(f"- [{b.id}] {b.character_id}: {b.beat}" for b in elsewhere)

    block = f"""# What this scene is responsible for (from the macro arc — by id)

## Arc beats this scene must deliver, as events on the page
{mine_lines}"""

    if other_lines:
        block += f"""

## Beats belonging to other scenes of this chapter — do NOT deliver them here
{other_lines}"""

    return f"""{block}

## The chapter's ledger duties (deliver them where they belong, not all in this scene)
{_ledger_block(spec, canon)}"""


def _chapter_frame(spec: ChapterSpec, arc: MacroArc) -> str:
    act = arc.act_for(spec.chapter)
    tension = next((t for t in arc.tension_curve if t.chapter == spec.chapter), None)
    entry = "\n".join(f"- {s.key}: {s.value}" for s in spec.entry_state) or "- (nothing carried in)"
    exit_ = "\n".join(f"- {s.key}: {s.value}" for s in spec.exit_state) or "- (nothing recorded)"

    return f"""# Chapter {spec.chapter}: {spec.title}

Purpose (what is different about the story after this chapter): {spec.purpose}
POV character (canon id): {spec.pov_character_id}
Book shape: {arc.shape}
Act: {act.number if act else '?'} — {act.purpose if act else '(none)'}
Intended pressure here: {tension.tension if tension else '?'}/10 ({tension.note if tension else ''})

## State as the chapter opens
{entry}

## State that must be true as it closes
{exit_}"""


def _scene_prompt(
    *,
    spec: ChapterSpec,
    canon: StoryModel,
    arc: MacroArc,
    author: AuthorModel,
    scene: SceneSpec,
    index: int,
    previous_tail: str,
    previous_is_chapter: bool,
    guidance: str = "",
) -> str:
    language = _language(canon)
    continuity = (
        f"""# Continuity — the end of {'the previous chapter' if previous_is_chapter else 'the previous scene'}
Continue from this. Do not recap it, do not repeat its images, and do not contradict it.

{previous_tail}"""
        if previous_tail.strip()
        else "# Continuity\nThis is the opening of the chapter. Nothing precedes it."
    )

    ruling = (
        f"""# Binding ruling (already adjudicated — follow it, do not re-litigate it)
{guidance}

"""
        if guidance.strip()
        else ""
    )

    return f"""{_scene_slice(spec, canon, scene)}

{author.voice_block()}

{ruling}{_chapter_frame(spec, arc)}

{scene_assignment_block(spec, arc, canon, scene)}

# The scene to write: {scene.id} (scene {index} of {len(spec.scenes)})
- location: {scene.location}
- present (canon ids): {', '.join(scene.character_ids) or '(none)'}
- intent — the work this scene does that no other scene does: {scene.intent}
- turn — what is true at its end that was not true at its start: {scene.turn}

{continuity}

## Task
Write scene {scene.id}. Prose only.

Rules:
- Write it in {language}. Every word of the prose is in {language}, including dialogue.
- The canon slice above is the source of truth. Use the canonical names and the aliases it lists;
  do not coin a new name, title, role or relationship for anyone, and do not give anyone a
  profession, a history or a possession the slice does not give them.
- Invent texture freely; invent facts never. A fact you need but were not given is a signal to
  write around the gap, not to fill it.
- Deliver the turn. If the scene ends where it began, it does not exist.
- Deliver the beats named above by id — as things that happen on the page, not as narration
  reporting that they happened.
- Only the people listed as present are present.
- No summary of what came before, no statement of the theme, no explaining a character's
  psychology to the reader. Show it happening or leave it out.
- Output the scene's prose alone: no heading, no scene id, no divider, no commentary."""


def _repair_prompt(
    *,
    unit: str,
    current: str,
    issues: List[Issue],
    canon_block: str,
    language: str,
    regenerate_prompt: str,
) -> str:
    """
    The repair contract: fix what was flagged, change nothing else, and never invent a fact.

    When the unit came back empty there is nothing to repair, so this hands back the original brief
    instead of asking a model to surgically edit a blank page.
    """
    if not current.strip() and regenerate_prompt.strip():
        return f"""{regenerate_prompt}

## Note on your previous attempt
It returned nothing usable:
{format_issues(issues)}

Write the full text this time. Prose only."""

    return f"""{canon_block}

# The prose under repair: {unit}
{current}

# What is wrong with it
{format_issues(issues)}

## Task
Return the corrected {unit}, in full, in {language}.

Rules — these are the whole job:
- Change ONLY the spans the issues above name. Every other sentence comes back byte-identical.
  This is an edit, not a rewrite; if you find yourself improving an unflagged line, stop.
- Each issue names the smallest change that resolves it. Make that change and no larger one.
- Where an issue is a contradiction with canon, **canon wins**. Correct the prose to match the
  canon slice above. You may not invent a fact, a reason, a backstory or a coincidence that makes
  the contradiction acceptable — a bridging fact is a worse failure than the one you were sent to
  fix. If the contradiction cannot be resolved by changing the prose, leave the passage and say
  nothing; the escalation path exists for that case, and it is not yours.
- Do not add material to compensate for what you cut, and do not restate the issues in the prose.
- Output the corrected prose alone: no heading beyond what is already there, no commentary."""


def _deterministic_issues(text: str, unit: str, min_chars: int) -> List[Issue]:
    """The cheap gate: nothing here needs a model, so it runs before anything that does."""
    stripped = text.strip()
    if not stripped:
        return [Issue("prose.empty", Severity.BLOCKING, f"{unit} came back empty", unit)]
    if len(stripped) < min_chars:
        return [Issue(
            "prose.stub", Severity.BLOCKING,
            f"{unit} is {len(stripped)} characters — a stub, not prose (minimum {min_chars})", unit)]
    return []


def _split_scenes(text: str) -> List[str]:
    """Recover the scene list from assembled markdown, so a chapter-level repair stays consistent."""
    lines = text.lstrip().split("\n")
    body = "\n".join(lines[1:]) if lines and lines[0].startswith("# ") else text
    return [part.strip() for part in body.split(f"\n{SCENE_DIVIDER}\n") if part.strip()]


def assemble_chapter(title: str, scenes: Sequence[str]) -> str:
    return f"# {title}\n\n" + f"\n\n{SCENE_DIVIDER}\n\n".join(s.strip() for s in scenes)


async def _repair_loop(
    *,
    stage: str,
    unit: str,
    text: str,
    evaluate: Callable[[str], Awaitable[List[Issue]]],
    repair_prompt: Callable[[str, List[Issue]], str],
    llm: StructuredLLM,
    model: str,
    max_tokens: int,
    tracer: Tracer,
    max_repairs: int,
) -> Tuple[str, List[Issue], int]:
    """Check → repair → re-check, bounded. Returns the best text reached and its remaining issues."""
    issues = await evaluate(text)
    repairs = 0

    while blocking(issues) and repairs < max_repairs:
        repairs += 1
        prompt = repair_prompt(text, blocking(issues))
        text = await llm.generate(prompt=prompt, system=SYSTEM, model=model, max_tokens=max_tokens)
        tracer.record(
            f"{stage}_repair_{repairs}",
            prompt=prompt,
            system=SYSTEM,
            model=model,
            artifact=text,
            note=f"{len(blocking(issues))} blocking issues",
        )
        issues = await evaluate(text)

    return text, issues, repairs


SELECTION_SYSTEM = """You are the Selector in an autonomous novel pipeline.

Several independent drafts of the same scene were written from the same assignment. You pick one.
You did not write any of them and you have no stake in any of them.

You are NOT checking correctness. Other readers, with the canon in hand, do that after you, and they
can repair small errors in whatever you choose. Picking the tidiest draft is therefore the one
mistake that cannot be undone later: correctness can be added to a living scene, but life cannot be
added to a correct one."""

SELECTION_RUBRIC = """Choose the draft that is most ALIVE.

The pipeline's whole tendency is toward the safe middle, so your bias must run the other way. Prefer:

1. **The one that surprised you.** A move you did not see coming, an image that is odd and exactly
   right, a line of dialogue that answers a question nobody asked. If two drafts are equally
   competent and one startled you, that one.
2. **The one that trusts the reader.** Prose that states the situation and stops, over prose that
   also explains what it means. A gesture left unglossed beats a gesture plus its interpretation.
3. **The one that risks something.** A scene that commits to a strange choice and lives with it, over
   one that hedges. Flatness is a failure mode; awkward ambition usually is not.
4. **The one with the sharper turn.** Something must be different at the end than at the start. Prefer
   the draft where that difference costs somebody something.

Reject: the draft that reads like a summary of the assignment; the one where every sentence does the
job the outline gave it and nothing more; the one whose emotional content is announced rather than
enacted; the one that could have been written from the plan alone without imagining the scene.

Do not prefer a draft for being longer, more ornate, or more eventful. Density is not life. A quiet
scene that is exactly observed beats a loud one that is generic.

Return the index of your choice and one sentence on what the others lacked."""


class CandidateChoice(BaseModel):
    """Which draft survives. One call, regardless of how many candidates there are."""

    model_config = ConfigDict(extra="forbid")

    chosen_index: int = Field(description="0-based index of the chosen draft.")
    reasoning: str = Field(description="One sentence: what this draft has that the others do not.")


async def _generate_candidates(
    *,
    prompt: str,
    n: int,
    llm: StructuredLLM,
    model: str,
    max_tokens: int,
    tracer: Tracer,
    unit: str,
    min_chars: int,
) -> List[str]:
    """
    Draw `n` independent drafts of one unit and drop the ones that are stubs.

    Identical prompts on purpose: the spread comes from sampling, not from asking for "a darker
    version" — steering each draft toward a different adjective would make the choice a choice
    between instructions rather than between imaginations.
    """
    candidates: List[str] = []
    for i in range(n):
        text = await llm.generate(prompt=prompt, system=SYSTEM, model=model, max_tokens=max_tokens)
        tracer.record(
            f"{unit}_prose_candidate_{i}", prompt=prompt, system=SYSTEM, model=model, artifact=text
        )
        if not _deterministic_issues(text, unit, min_chars):
            candidates.append(text)
    return candidates


async def _select(
    *,
    candidates: List[str],
    assignment: str,
    llm: StructuredLLM,
    model: str,
    tracer: Tracer,
    unit: str,
) -> str:
    """Pick the most alive draft. Falls back to the first on a nonsense index rather than failing."""
    if len(candidates) == 1:
        return candidates[0]

    blocks = "\n\n".join(
        f"## Draft {i}\n{text.strip()}" for i, text in enumerate(candidates)
    )
    prompt = f"""{assignment}

# The drafts
{blocks}

{SELECTION_RUBRIC}"""
    choice = await llm.parse(
        prompt=prompt, schema=CandidateChoice, system=SELECTION_SYSTEM, model=model, max_tokens=2000
    )
    tracer.record(
        f"{unit}_prose_selection",
        prompt=prompt,
        system=SELECTION_SYSTEM,
        model=model,
        artifact=choice,
        note=f"chose {choice.chosen_index} of {len(candidates)}",
    )
    if 0 <= choice.chosen_index < len(candidates):
        return candidates[choice.chosen_index]
    return candidates[0]


async def write_chapter(
    *,
    spec: ChapterSpec,
    canon: StoryModel,
    arc: MacroArc,
    author: AuthorModel,
    llm: StructuredLLM,
    previous_tail: str = "",
    checkers: Sequence[ProseChecker] = (),
    tracer: Optional[Tracer] = None,
    model: str = "opus",
    max_repairs: int = 2,
    strict: bool = True,
    max_tokens: int = 32000,
    min_scene_chars: int = MIN_SCENE_CHARS,
    guidance: str = "",
    n_candidates: int = 1,
    selection_model: str = "sonnet",
) -> ProseResult:
    """
    Write one chapter, scene by scene, grounded in canon and checked at both scales.

    Never one chapter-shaped call: each scene is generated from its own canon slice and its own
    assignment, so what the scene was for is in the prompt that wrote it, and what went wrong in it
    is localised to it.

    `guidance` carries a binding ruling from adjudication (§6.5) into a re-attempt: when a first
    attempt escalated and the adjudicator ruled, the ruling rides into every scene prompt so the
    re-write is bound by it rather than re-discovering the same conflict.
    """
    tracer = tracer or Tracer(None)
    language = _language(canon)
    unit_prefix = f"ch{spec.chapter:02d}"

    def evaluator(unit: str, scene: Optional[SceneSpec]) -> Callable[[str], Awaitable[List[Issue]]]:
        async def evaluate(text: str) -> List[Issue]:
            issues = _deterministic_issues(text, unit, min_scene_chars)
            if issues:
                return issues  # a stub is not worth a checker call
            for checker in checkers:
                verdict = await checker.check_prose(
                    prose=text, canon=canon, spec=spec, author=author, scene=scene
                )
                if verdict.decision == Decision.ESCALATE:
                    raise Escalation(unit, verdict.conflict, verdict)
                issues += verdict.to_issues(checker.name)
            return issues
        return evaluate

    scenes: List[str] = []
    issues: List[Issue] = []
    repairs = 0
    tail = previous_tail
    previous_is_chapter = True

    for index, scene in enumerate(spec.scenes, start=1):
        unit = f"{unit_prefix}_{scene.id}"
        prompt = _scene_prompt(
            spec=spec, canon=canon, arc=arc, author=author, scene=scene,
            index=index, previous_tail=tail, previous_is_chapter=previous_is_chapter,
            guidance=guidance,
        )
        if n_candidates > 1:
            # Selection before repair. Repair moves a draft toward the rubric, which is exactly what
            # makes prose grey — every iteration trades surprise for compliance. Choosing among
            # independent drafts preserves the spread instead of collapsing it, so the variance is
            # spent on finding a live scene rather than sanding one down.
            candidates = await _generate_candidates(
                prompt=prompt, n=n_candidates, llm=llm, model=model, max_tokens=max_tokens,
                tracer=tracer, unit=unit, min_chars=min_scene_chars,
            )
            if candidates:
                text = await _select(
                    candidates=candidates, assignment=prompt, llm=llm,
                    model=selection_model, tracer=tracer, unit=unit,
                )
            else:
                # Every candidate was a stub. Keep the last one so the repair loop sees the real
                # failure and reports it, rather than raising something less informative here.
                text = await llm.generate(
                    prompt=prompt, system=SYSTEM, model=model, max_tokens=max_tokens
                )
        else:
            text = await llm.generate(prompt=prompt, system=SYSTEM, model=model, max_tokens=max_tokens)
        tracer.record(f"{unit}_prose", prompt=prompt, system=SYSTEM, model=model, artifact=text)

        text, scene_issues, scene_repairs = await _repair_loop(
            stage=f"{unit}_prose",
            unit=f"scene {scene.id}",
            text=text,
            evaluate=evaluator(unit, scene),
            repair_prompt=lambda current, flagged, _s=scene, _p=prompt: _repair_prompt(
                unit=f"scene {_s.id}",
                current=current,
                issues=flagged,
                canon_block=_scene_slice(spec, canon, _s),
                language=language,
                regenerate_prompt=_p,
            ),
            llm=llm, model=model, max_tokens=max_tokens, tracer=tracer, max_repairs=max_repairs,
        )

        repairs += scene_repairs
        issues += scene_issues
        if strict and blocking(scene_issues):
            raise ProseGateFailed(blocking(issues))

        scenes.append(text.strip())
        tail = _tail(text)
        previous_is_chapter = False

    chapter_text = assemble_chapter(spec.title, scenes)
    tracer.record(
        f"{unit_prefix}_prose_assembled",
        prompt="",
        model=model,
        artifact=chapter_text,
        note=f"{len(scenes)} scenes",
    )

    # Some failures only exist at chapter scale — an image used twice, a turn that lands in two
    # scenes, a chapter that adds up to less than its parts. The scene pass cannot see them.
    chapter_text, chapter_issues, chapter_repairs = await _repair_loop(
        stage=f"{unit_prefix}_prose",
        unit=f"chapter {spec.chapter}",
        text=chapter_text,
        evaluate=evaluator(unit_prefix, None),
        repair_prompt=lambda current, flagged: _repair_prompt(
            unit=f"chapter {spec.chapter}",
            current=current,
            issues=flagged,
            canon_block=_chapter_slice(spec, canon),
            language=language,
            regenerate_prompt="",
        ),
        llm=llm, model=model, max_tokens=max_tokens, tracer=tracer, max_repairs=max_repairs,
    )

    repairs += chapter_repairs
    issues += chapter_issues
    if chapter_repairs:
        scenes = _split_scenes(chapter_text) or scenes

    result = ProseResult(
        chapter=spec.chapter, text=chapter_text, scenes=scenes, issues=issues, repairs=repairs
    )
    if strict and not result.is_valid:
        raise ProseGateFailed(blocking(issues))
    return result
