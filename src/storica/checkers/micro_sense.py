"""
The Micro-Sense checker (DESIGN §6, failure class #3: *locally fluent but nonsensical*).

The other conformance readers ask whether the unit agrees with canon and whether it sounds like
the author. This one asks the question neither of them can: **does this paragraph mean anything?**
Prose can contradict nothing, sound exactly like Dürrenmatt, and still be a sequence of well-formed
sentences describing an event that could not happen, or an abstraction standing where the event
should be. That is
what v1 shipped whenever the critic's weighted average cleared the gate (F8) — a competent draft
was never read closely enough for anyone to notice that a paragraph was hollow.

So this checker reads **paragraph by paragraph** against the canon slice, and every issue it raises
must quote the span it objects to: a finding that cannot be localised cannot be repaired without
rewriting the unit, and a rewrite is exactly how the F12 corruption amplifier started.

Voice belongs to `AuthorVoiceChecker`, contradiction belongs to `CanonConsistencyChecker`. This one
stays on grounding, coherence and load-bearing language.

"Grounding" is the writer's invention policy (`canon/invention.py`), read byte-for-byte from the same
constant the writer is given. This reader used to call every unglossed date a hallucination while
the writer was told to invent texture; one chapter was quarantined in that gap (FINDINGS C7). A
specific the policy permits is not an issue at all — reconcile records it into canon.
"""

from __future__ import annotations

import re
from typing import List, Optional

from ..authors import AuthorModel
from ..llm import stage_model
from ..canon import INVENTION_POLICY, StoryModel
from ..plan import ChapterSpec, SceneSpec
from .base import Verdict
from .prose_base import ProseCheckerBase, unit_label
from ..agents import block as agent_block, system as agent_system

# The instructions live in agents/micro_sense.md.
SYSTEM = agent_system("micro_sense")

# In agents/micro_sense.md, section <!-- rubric -->.
MICRO_RUBRIC = agent_block("micro_sense", "rubric")


def _numbered_paragraphs(prose: str) -> str:
    """Number the paragraphs so an issue can point at one instead of at the whole unit."""
    paragraphs: List[str] = [p.strip() for p in re.split(r"\n\s*\n", prose.strip()) if p.strip()]
    if not paragraphs:
        return "(empty)"
    return "\n\n".join(f"[P{i}] {p}" for i, p in enumerate(paragraphs, start=1))


class MicroSenseChecker(ProseCheckerBase):
    """Fresh-context paragraph reader: grounded, coherent, load-bearing — or an issue with a quote."""

    name = "micro_sense"

    SYSTEM = SYSTEM
    DEFAULT_MODEL = stage_model("micro_sense")
    DEFAULT_MAX_TOKENS = 8000

    async def check_prose(
        self,
        *,
        prose: str,
        canon: StoryModel,
        spec: ChapterSpec,
        author: AuthorModel,
        scene: Optional[SceneSpec] = None,
        draw: int = 1,
    ) -> Verdict:
        # The slice is scoped to exactly what the unit touches: a scene is judged against its own
        # cast, so a hallucinated third person shows up as absent from the slice rather than being
        # quietly covered by the chapter's wider roster.
        slice_text = self.scene_slice(canon, spec, scene)
        unit = unit_label(spec, scene)

        if scene:
            header = f"""# Unit under review: chapter {spec.chapter}, scene {scene.id}
- location: {scene.location}
- present: {', '.join(scene.character_ids) or '(nobody listed)'}
- scene intent: {scene.intent}
- scene turn: {scene.turn}
- chapter purpose (context): {spec.purpose}"""
        else:
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

{INVENTION_POLICY}

{MICRO_RUBRIC}"""
        return await self.check(prompt=prompt, unit=unit, draw=draw)
