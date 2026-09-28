"""
The Canon-Consistency checker for prose (DESIGN §6, failure class #1: semantic contradiction).

The deterministic validator has already proved that the ids line up, the cast is legal and the
ledger balances. What it cannot see is the part that is only visible in the sentences: a fact that
has quietly changed meaning, a character behaving as someone they are not, a timeline that cannot
have happened, a name used for the wrong person. That is precisely the seam v1 lost the book in —
the writer recast Rutz the priest as a creditor (F9), the guardian wrote the slip into the bible as
fact (F10), and everything downstream was built on it.

Two rules follow from that history and are non-negotiable in this checker's prompt:

- It **never proposes a canon edit.** Canon is corrected by the adjudicator against immutable ground
  truth (§6.5), never by a reader who has just seen one chapter.
- It **never invents a bridging fact.** "He is a priest *and* a private creditor" is how a plain
  contradiction became elaborated false canon in v1 (F11), and how the reviser then made the book
  worse while looking better (F12). When the canon itself is what looks wrong, the only permitted
  answer is `escalate` with the conflict described.
"""

from __future__ import annotations

from typing import Optional

from ..authors import AuthorModel
from ..llm import stage_model
from ..canon import StoryModel
from ..plan import ChapterSpec, SceneSpec
from .base import Verdict
from .prose_base import ProseCheckerBase, unit_label
from ..agents import block as agent_block, system as agent_system

# The instructions live in agents/canon_consistency.md.
SYSTEM = agent_system("canon_consistency")

# In agents/canon_consistency.md, section <!-- rubric -->.
CONSISTENCY_RUBRIC = agent_block("canon_consistency", "rubric")


def _name_registry(canon: StoryModel) -> str:
    """
    Every canon character, not just the ones in scene.

    Detecting that a name has been attached to the wrong person needs the whole roster: the slice
    alone cannot tell you that "Rutz" already belongs to someone who is not in this scene (F7/F9).
    """
    rows = [
        f"- {cid} = {ch.canonical_name} (also called: {', '.join(ch.aliases) or 'nothing else'}) — {ch.role.value}"
        for cid, ch in canon.characters.items()
    ]
    return (
        "# Name registry (COMPLETE — every character that exists in this novel)\n"
        "Any personal name in the prose must resolve to exactly one entry below. A name that is not "
        "here belongs to nobody.\n" + ("\n".join(rows) or "- (canon has no characters)")
    )


class CanonConsistencyChecker(ProseCheckerBase):
    """Fresh-context reader for semantic contradiction between prose and canon."""

    name = "canon_consistency"

    SYSTEM = SYSTEM
    DEFAULT_MODEL = stage_model("canon_consistency")
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
        slice_text = self.scene_slice(canon, spec, scene)
        unit = unit_label(spec, scene)

        if scene:
            header = f"""# Unit under review: chapter {spec.chapter}, scene {scene.id}
- location: {scene.location}
- canon ids that may appear: {', '.join(scene.character_ids) or '(nobody listed)'}
- scene intent: {scene.intent}
- scene turn: {scene.turn}
- chapter purpose (context): {spec.purpose}"""
        else:
            scenes = "\n".join(
                f"  - [{s.id}] {s.location} — present: {', '.join(s.character_ids)} | "
                f"intent: {s.intent} | turn: {s.turn}"
                for s in spec.scenes
            ) or "  - (no scenes specced)"
            header = f"""# Unit under review: chapter {spec.chapter} — {spec.title}
- chapter purpose: {spec.purpose}
- POV: {spec.pov_character_id}
- canon ids that may appear: {', '.join(spec.present_character_ids) or '(nobody listed)'}
- scenes it was written from:
{scenes}"""

        entry = "\n".join(f"  - {f.key}: {f.value}" for f in spec.entry_state) or "  - (none)"
        exit_ = "\n".join(f"  - {f.key}: {f.value}" for f in spec.exit_state) or "  - (none)"

        prompt = f"""{slice_text}

{_name_registry(canon)}

# Author (context only — voice is judged by a different reader): {author.name}

{header}

# Canonical state this unit was given
- entry state (true as it opens):
{entry}
- exit state (must be true as it closes):
{exit_}

# The prose
{prose}

{CONSISTENCY_RUBRIC}"""
        return await self.check(prompt=prompt, unit=unit, draw=draw)
