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
from ...agents import block as agent_block, system as agent_system

SCENE_DIVIDER = "* * *"

# How much of the *previous chapter* rides into the first scene of the next. Enough to inherit
# rhythm, sentence length and the temperature of the last image — not so much that the model starts
# continuing a paragraph instead of opening a chapter. Earlier chapters reach the writer as canon
# (reconcile), not as text.
TAIL_CHARS = 1500

# Within a chapter the writer sees every scene already written, not an 800-character tail. With the
# tail alone, scene 3 did not know what was said in scene 1, so it could repeat an image, re-deliver
# a line, or contradict a gesture no canon records. A chapter's scenes are short; this cap only
# protects against a runaway one, and past it the most recent text is kept.
CHAPTER_SO_FAR_CHARS = 24000

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


# The instructions live in agents/prose.md.
SYSTEM = agent_system("prose")


def _language(canon: StoryModel) -> str:
    code = (canon.constraints.language or "en").strip()
    return _LANGUAGE_NAMES.get(code.lower(), code)


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


# In agents/prose.md, section <!-- before-you-write -->.
BEFORE_YOU_WRITE = agent_block("prose", "before-you-write")


def _continuity_block(previous_chapter_tail: str, chapter_so_far: str) -> str:
    if chapter_so_far.strip():
        text = chapter_so_far.strip()
        if len(text) > CHAPTER_SO_FAR_CHARS:
            text = "[…]\n" + text[-CHAPTER_SO_FAR_CHARS:]
        return f"""# Continuity — this chapter so far
Everything below is already written and fixed. Continue from its last line. Do not recap it, do not
reuse its images or its lines, and do not contradict anything it shows — a gesture, an object, who
said what.

{text}"""
    if previous_chapter_tail.strip():
        return f"""# Continuity — the end of the previous chapter
This scene opens a new chapter. Do not recap the previous one, do not repeat its images, and do not
contradict it.

{previous_chapter_tail}"""
    return "# Continuity\nThis is the opening of the book. Nothing precedes it."


def _scene_prompt(
    *,
    spec: ChapterSpec,
    canon: StoryModel,
    arc: MacroArc,
    author: AuthorModel,
    scene: SceneSpec,
    index: int,
    previous_chapter_tail: str = "",
    chapter_so_far: str = "",
    guidance: str = "",
) -> str:
    language = _language(canon)
    continuity = _continuity_block(previous_chapter_tail, chapter_so_far)

    ruling = (
        f"""# Binding ruling (already adjudicated — follow it, do not re-litigate it)
{guidance}

"""
        if guidance.strip()
        else ""
    )

    return f"""{_scene_slice(spec, canon, scene)}

{author.writer_block()}

{ruling}{_chapter_frame(spec, arc)}

{scene_assignment_block(spec, arc, canon, scene)}

# The scene to write: {scene.id} (scene {index} of {len(spec.scenes)})
- location: {scene.location}
- present (canon ids): {', '.join(scene.character_ids) or '(none)'}
- intent — the work this scene does that no other scene does: {scene.intent}
- turn — what is true at its end that was not true at its start: {scene.turn}

{continuity}

{BEFORE_YOU_WRITE}

## Task
Write scene {scene.id}. Prose only.

Rules:
- Write it in {language}. Every word of the prose is in {language}, including dialogue.
- The canon slice above is the source of truth. Use the canonical names and the aliases it lists;
  do not coin a new name, title, role or relationship for anyone, and do not give anyone an
  office, a history or a secret the slice does not give them.
- Invent within the policy in your instructions: the texture and the minor specifics of the world
  are yours to decide; identity, relationships, who knows what, and the story's open questions are
  not.
- Deliver the turn. If the scene ends where it began, it does not exist.
- Deliver the beats named above by id — as things that happen on the page, not as narration
  reporting that they happened.
- Only the people listed as present are present, apart from unnamed walk-ons the scene needs.
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
