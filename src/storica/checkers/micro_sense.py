"""
The Micro-Sense checker (DESIGN §6, failure class #3: *locally fluent but nonsensical*).

The other two prose readers ask whether the unit agrees with canon and whether it sounds like the
author. This one asks the question neither of them can: **does this paragraph mean anything?**
Prose can contradict nothing, sound exactly like Dürrenmatt, and still be a sequence of well-formed
sentences describing an event that could not happen, made of details nobody ever decided on. That is
what v1 shipped whenever the critic's weighted average cleared the gate (F8) — a competent draft
was never read closely enough for anyone to notice that a paragraph was hollow.

So this checker reads **paragraph by paragraph** against the canon slice, and every issue it raises
must quote the span it objects to: a finding that cannot be localised cannot be repaired without
rewriting the unit, and a rewrite is exactly how the F12 corruption amplifier started.

Voice belongs to `AuthorVoiceChecker`, contradiction belongs to `CanonConsistencyChecker`. This one
stays on grounding, coherence and load-bearing language.
"""

from __future__ import annotations

import re
from typing import List, Optional

from ..authors import AuthorModel
from ..canon import StoryModel, canon_slice
from ..llm import StructuredLLM
from ..plan import ChapterSpec, SceneSpec
from ..trace import Tracer
from .base import Checker, Verdict

SYSTEM = """You are a Micro-Sense checker in an autonomous novel pipeline.

You did not write this prose and you have no memory of how it was produced — you are a fresh reader
with the canon slice in one hand and the text in the other. Judge only what is on the page.

You do NOT rewrite, and you do NOT score. A global "quality score" is worthless here: it lets a
paragraph that means nothing hide inside a chapter that reads well. Return a verdict with a list of
issues instead, each one pinned to a paragraph and a quoted span:
- 'pass'     — every paragraph is grounded, the situation works, and no sentence is doing nothing.
- 'revise'   — fixable in place; every issue names the smallest edit that fixes it.
- 'escalate' — the paragraph cannot be made to make sense because the canon slice itself is silent
               or self-contradictory on something the scene depends on. Say so in `conflict`. Do NOT
               invent the missing fact and do NOT tell the writer to invent one.

You are not the voice checker and not the continuity checker. Say nothing about style, rhythm or
whether this sounds like the author, and nothing about what the chapter contributes to the plot.
Your subject is the sentence and the paragraph: is it grounded, does it cohere, is it load-bearing."""

MICRO_RUBRIC = """Read the unit one numbered paragraph at a time. For each paragraph, in this order:

1. **Is every concrete detail grounded?** Names, professions, objects, places, distances, dates,
   procedures, weather, who owns what, who knows what — each must come from the canon slice or
   follow plainly from it. A specific detail that has no canon basis is a hallucination: the writer
   made it up to fill the sentence, and the next chapter will be built on it. Flag it and quote it.
2. **Does the situation actually work?** Walk the physical logic: where each body is, what each hand
   is holding, what can be seen and heard from where, how long a thing takes. Then the social logic:
   what this character would plausibly say to *this* person, in this place, given what they know.
   A scene where two people speak as if alone in a full room, or where a man signs a document he was
   never handed, is broken however smoothly it reads.
3. **Is the language load-bearing?** Sentences that could be deleted with nothing lost are the
   symptom this checker exists for. Test each one: if you cut it, what does the reader no longer
   know or feel? Atmosphere that repeats atmosphere already established is filler.
4. **Is the event on the page, or only an abstraction of it?** "Die Spannung im Raum wuchs" instead
   of the thing that happened; "sie sprachen über den Toten" instead of what was said. Abstraction
   standing in for the concrete event is the most common way a paragraph pretends to work.
5. **Do the sentences follow from each other?** A paragraph whose second sentence does not proceed
   from its first — a jump in place, in time, in who is speaking, or a claim the previous sentence
   contradicts — is a broken paragraph even if each sentence is fine alone.

How to report:
- `unit`: the paragraph marker plus a quoted span of at most twelve words, e.g.
  `P4: "griff nach dem Formular, das er nie erhalten hatte"`. An issue that quotes nothing forces a
  rewrite instead of an edit — always quote.
- `canon_ref`: the canon id the detail should have come from (character id, world_fact key,
  timeline id, motif id), or empty when canon simply says nothing.
- `fix_hint`: the smallest edit — "cut this sentence", "replace the age with the canon fact",
  "state what he actually said". Never "rewrite the paragraph".

Blocking vs warning — be concrete, not squeamish:
- BLOCKING: an invented detail the scene leans on (an object, a fact, a person, a place that canon
  does not have); a situation whose physical or social logic cannot happen as written; the scene's
  own event replaced by an abstraction of it; a paragraph whose sentences contradict each other.
- WARNING: a single filler sentence in a paragraph that otherwise works; a slack transition; a
  flourish you would cut but that costs the reader nothing; an unglossed detail that is consistent
  with canon but that canon never mentions.
- Not an issue at all: a choice you would have made differently. You are not the writer."""


def _numbered_paragraphs(prose: str) -> str:
    """Number the paragraphs so an issue can point at one instead of at the whole unit."""
    paragraphs: List[str] = [p.strip() for p in re.split(r"\n\s*\n", prose.strip()) if p.strip()]
    if not paragraphs:
        return "(empty)"
    return "\n\n".join(f"[P{i}] {p}" for i, p in enumerate(paragraphs, start=1))


class MicroSenseChecker(Checker):
    """Fresh-context paragraph reader: grounded, coherent, load-bearing — or an issue with a quote."""

    name = "micro_sense"

    def __init__(
        self,
        llm: StructuredLLM,
        *,
        model: str = "sonnet",
        max_tokens: int = 8000,
        tracer: Optional[Tracer] = None,
    ):
        self.llm = llm
        self.model = model
        self.max_tokens = max_tokens
        self.tracer = tracer or Tracer(None)

    async def check(self, *, prompt: str, unit: str) -> Verdict:
        verdict = await self.llm.parse(
            prompt=prompt,
            schema=Verdict,
            system=SYSTEM,
            model=self.model,
            max_tokens=self.max_tokens,
        )
        self.tracer.record(
            f"micro_sense_check_{unit}",
            prompt=prompt,
            system=SYSTEM,
            model=self.model,
            artifact=verdict,
            note=verdict.decision.value,
        )
        return verdict

    async def check_prose(
        self,
        *,
        prose: str,
        canon: StoryModel,
        spec: ChapterSpec,
        author: AuthorModel,
        scene: Optional[SceneSpec] = None,
    ) -> Verdict:
        # The slice is scoped to exactly what the unit touches: a scene is judged against its own
        # cast, so a hallucinated third person shows up as absent from the slice rather than being
        # quietly covered by the chapter's wider roster.
        character_ids = scene.character_ids if scene else spec.present_character_ids
        slice_text = canon_slice(
            canon,
            character_ids=character_ids,
            motif_ids=[*spec.setups, *spec.payoffs],
            promise_ids=[*spec.promises_made, *spec.promises_kept],
        )

        if scene:
            unit = f"ch{spec.chapter:02d}_{scene.id}"
            header = f"""# Unit under review: chapter {spec.chapter}, scene {scene.id}
- location: {scene.location}
- present: {', '.join(scene.character_ids) or '(nobody listed)'}
- scene intent: {scene.intent}
- scene turn: {scene.turn}
- chapter purpose (context): {spec.purpose}"""
        else:
            unit = f"ch{spec.chapter:02d}"
            scenes = "\n".join(
                f"  - [{s.id}] {s.location} — intent: {s.intent} | turn: {s.turn}" for s in spec.scenes
            ) or "  - (no scenes specced)"
            header = f"""# Unit under review: chapter {spec.chapter} — {spec.title}
- chapter purpose: {spec.purpose}
- POV: {spec.pov_character_id}
- present: {', '.join(spec.present_character_ids) or '(nobody listed)'}
- scenes it was written from:
{scenes}"""

        entry = "\n".join(f"  - {f.key}: {f.value}" for f in spec.entry_state) or "  - (none)"
        exit_ = "\n".join(f"  - {f.key}: {f.value}" for f in spec.exit_state) or "  - (none)"

        prompt = f"""{slice_text}

# Author (context only — voice is judged by a different reader, not by you): {author.name}

{header}

# Canonical state around this unit
- as it opens:
{entry}
- as it closes:
{exit_}

# The prose, paragraph by paragraph
{_numbered_paragraphs(prose)}

{MICRO_RUBRIC}"""
        return await self.check(prompt=prompt, unit=unit)
