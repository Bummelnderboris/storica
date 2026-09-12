"""
Everything the prose agent is handed: its system prompt, its canon slices, and its assignment.

Three v1 failures are rules here rather than hopes:

- **truncated context.** v1 threaded `raw_blueprint[:800]` into the writer. Every call here carries
  `canon_slice(...)` for exactly the characters, motifs and promises the unit touches — the complete
  canonical truth about what it handles, never a prefix of a summary.
- **canon drift the critic could not see.** The slice is in the prompt as source of truth, the
  writer is forbidden from inventing facts, and every checker judging the unit gets the same slice.
- **implied intent.** The beats to advance and the setups/payoffs to deliver are named *by id*. An
  agent that is only hinted at what a scene is for will write something fluent that is for nothing.
"""

from __future__ import annotations

from typing import List

from ...authors import AuthorModel
from ...canon import Issue, StoryModel, unit_slice
from ...plan import ChapterSpec, MacroArc, SceneSpec
from ..gate import format_issues

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
    return unit_slice(canon, spec, scene)


def _chapter_slice(spec: ChapterSpec, canon: StoryModel) -> str:
    return unit_slice(canon, spec, None)


def _ledger_assignment_block(spec: ChapterSpec, canon: StoryModel) -> str:
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
{_ledger_assignment_block(spec, canon)}"""


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
