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
from ..canon import StoryModel, canon_slice
from ..llm import StructuredLLM
from ..plan import ChapterSpec, SceneSpec
from ..trace import Tracer
from .base import Checker, Verdict

SYSTEM = """You are a Canon-Consistency checker in an autonomous novel pipeline.

You did not write this prose and you have no memory of how it was produced. The canon slice you are
given is the source of truth. The prose is the thing on trial. Where they disagree, the prose is
wrong — unless the canon itself is incoherent, and then see the escalation rule below.

A structural validator has already run: ids resolve, the cast is legal, the ledger balances. Do not
spend yourself on bookkeeping. Your job is the part a validator cannot see — meaning. A fact that
has quietly changed, a person acting as someone they are not, a sequence of events that cannot have
happened in that order, a relationship the behaviour contradicts, a name attached to the wrong body.

You do NOT rewrite, and you do NOT score. A consistency score is meaningless: one contradiction is a
contradiction. Return a verdict with a list of issues:
- 'pass'     — nothing in the prose contradicts the canon slice.
- 'revise'   — the prose contradicts canon and can be corrected toward canon in place.
- 'escalate' — the CANON is what looks wrong: two canon facts contradict each other, or the prose
               is right and canon is stale, or the scene as specced cannot happen given canon. Set
               `conflict` to a plain statement of the two things that cannot both be true.

Three absolute prohibitions:
1. **Never propose a change to canon.** Not as a fix_hint, not as a suggestion, not "canon should
   probably say X". You do not have the authority and you have not seen the ground truth the canon
   was built from. If canon looks wrong, escalate and describe the conflict — that is the whole
   mechanism.
2. **Never invent a bridging fact.** A bridging fact is any new claim that would make both sides of
   a contradiction true at once: "he is a priest AND a private creditor", "she was his widow AND his
   housekeeper", "the certificate was signed twice". This is not a resolution; it is a contradiction
   with an alibi, and every one of them survives into the next chapter as false canon. Flag the
   contradiction; do not reconcile it.
3. **Never treat the prose as evidence about the world.** If the prose asserts a fact canon does not
   have, that is the prose making something up, not canon being incomplete."""

CONSISTENCY_RUBRIC = """Check the prose against the canon slice on these six axes:

1. **Facts that changed meaning.** Profession, office, age, place of origin, what someone owns, what
   someone did, what someone knows and since when. The dangerous version is not a flat error but a
   drift: a doctor who examines like a policeman, a certificate that becomes a confession, a secret
   the prose treats as public. Quote the line and name the canon fact it displaces.
2. **Identity and role drift.** A character behaving as someone they are not — the village priest
   who acts as a creditor, the widow of the dead man who acts as the protagonist's housekeeper. Ask
   for each named person: does this behaviour belong to the role, relationships and facts canon
   records for them? This is the single most expensive failure in this pipeline's history. BLOCKING.
3. **Timeline.** Could this have happened in this order? Check anything the prose asserts about how
   long ago, how long it took, who was alive, who was present, and what was already known. An event
   that requires knowledge nobody had yet is a contradiction even if no date is stated.
4. **Relationships contradicted by behaviour.** Canon states relationships as types; prose states
   them as conduct. Two people canon calls old friends who deal with each other as strangers, or a
   creditor and debtor who behave as equals, contradict canon just as surely as a wrong name does.
5. **Names and referents.** Every name in the prose must resolve to exactly one canon character. A
   name attached to the wrong person, a canon character renamed, an unnamed body given a name canon
   does not have, or a brand-new named person nobody put in the cast — all BLOCKING. Use the name
   registry: the registry is complete, so a name that is not in it does not exist.
6. **Canonical state.** The prose must open in the entry state and close in the exit state it was
   given. A chapter that ends with somebody knowing something the exit state says they do not know
   is a contradiction the next chapter will inherit.
7. **Identity count — has anyone split or merged?** Every canon id is exactly one person. Count them
   in the prose. A single canon character written as *two* people (one carrying half their facts,
   one the other half, often with one left unnamed) is a split; two canon characters written as one
   is a merge. Both are BLOCKING, and both are easy to miss because every individual sentence reads
   correctly — the error is only visible when you ask "how many people is this text describing?"
   Check this explicitly for any character whose canon facts cover two roles at once: that is where
   a split hides, because each half looks plausible on its own.
8. **Knowledge state.** If a knowledge table is given, it is binding. A character may only act on,
   allude to or react to what it grants them. Someone written as certain of a fact they merely
   `suspect`, or as aware of one they are `unaware` of, is BLOCKING — and it is the failure the
   prose is most likely to commit, because a writer who knows a secret finds it hard to keep a
   character ignorant of it. Cite the knowledge id in `canon_ref`.

How to report:
- `unit`: a quoted span of at most twelve words from the prose. Never the whole unit.
- `canon_ref`: the exact canon id the prose contradicts — character id, world_fact key, timeline id,
  relationship, motif or promise id, or the entry/exit state key. An issue with no canon_ref is
  probably not a consistency issue; leave it to the other readers.
- `fix_hint`: the smallest correction **toward canon** — "call him Pfarrer, as canon does", "cut the
  clause claiming she was present", "restore the cause of death canon records". Never a canon edit,
  never a new fact, never "reconcile these".

Blocking vs warning:
- BLOCKING: every contradiction with canon, without exception. There is no such thing as a minor
  contradiction here — v1 shipped a broken book one small uncorrected slip at a time.
- WARNING: the prose asserts something specific that canon is simply silent about, and it does not
  contradict anything. Note it so it can be reconciled into canon later; do not treat it as an error.
- ESCALATE (not an issue list): the canon slice itself does not hold together, or holding the prose
  to canon would make the assigned scene impossible. Describe both sides in `conflict` and stop."""


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


class CanonConsistencyChecker(Checker):
    """Fresh-context reader for semantic contradiction between prose and canon."""

    name = "canon_consistency"

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
            f"canon_consistency_check_{unit}",
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
- canon ids that may appear: {', '.join(scene.character_ids) or '(nobody listed)'}
- scene intent: {scene.intent}
- scene turn: {scene.turn}
- chapter purpose (context): {spec.purpose}"""
        else:
            unit = f"ch{spec.chapter:02d}"
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
        return await self.check(prompt=prompt, unit=unit)
