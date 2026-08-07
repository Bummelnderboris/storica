# Storica Pipeline v2 — Design

> Status: **DRAFT for iteration.** Written after the 1:1 capture run (`story_output/pipeline_capture/`,
> findings F1–F12). This is the architecture spec + build plan for the redesign. No code changed yet.

---

## 0. The problem, stated precisely

The v1 pipeline is already top-down (topic→thesis→characters→architecture→blueprints→prose) and the
prose is genuinely good sentence-by-sentence. What fails is the **macro↔micro seam**:

- Plans (macro) are coherent. Sentences (micro) are coherent. The **translation and maintenance
  between them is not.** Over distance the model hallucinates details, mixes up facts, writes
  situations that don't cohere, and produces locally-fluent-but-meaningless paragraphs.
- Root cause #1 (**coherence**): each stage passed *prose* forward; the next stage *re-interpreted*
  it. Prose is lossy and re-readable, so meaning leaked at every hand-off. The story "bible" was
  seeded from prose, not ground truth — so one early slip (a priest logged as a creditor) became
  permanent and self-propagating (F6, F9, F10, F11, F12).
- Root cause #2 (**meaning**): the only gate was a weighted-average quality score (F8). It measures
  voice/quality, which competent drafts always pass, and has no notion of "did this paragraph
  *advance the intended arc* / *make sense* / *keep the story's promises*." Coherent ≠ meaningful.

**Design thesis:** hold intent in a *structured canon*, elaborate strictly top-down with
*just-in-time* detail, ground every generation in the *full relevant canon*, and put a layer of
*fresh-context verification/repair agents* at every seam whose job is coherence + meaning + micro-sense.

---

## 1. Principles

1. **Canon is the substrate; prose is only an output.** A single structured, versioned
   `story_model.json` is the source of truth. Every stage reads from it and writes to it. Prose is
   never re-parsed as truth — facts are extracted from prose and *validated into* canon.
2. **Top-down, but progressively elaborated — not a frozen mega-outline.** Never write level N
   without a *validated* level N−1. But elaborate level N **just-in-time** from the canon, not all
   levels up front. (A paragraph-level outline of a whole novel is itself novel-length and drifts.)
3. **Ground every generation in the full relevant canon.** Micro units are generated from the
   complete canonical slice they touch (all characters/facts/motifs in scene), never a truncated
   blueprint (kills the F5 `[:800]` problem). Macro intent rides *into* the micro call explicitly.
4. **Verify with fresh agents, not the generator.** The writer is blind to its own drift. Every seam
   gets an independent reader with the canon in hand and a sharp rubric and authority to pass /
   revise / escalate.
5. **Resolve conflicts to ground truth, never to the mutable bible.** When prose or a plan
   contradicts canon, repair toward an **immutable ground truth** (the original brief + the Phase-2
   canon locked at creation) — never let a downstream agent "reconcile" by inventing a bridging fact
   (kills F11/F12). Every resolution is a **binding, logged ruling** so it is never re-litigated.
6. **The author is a generative driver, not a paint job.** The author's obsessions and question-lines
   *select and shape which story gets told*, not just its style.
7. **Autonomous by default; the human touches only the front door.** The creator supplies a light
   brief (thoughts, question-lines, nudges) and the pipeline writes the whole novel unattended — the
   result is meant to *surprise the creator*. There are **no approval pauses** during generation.
   Escalations don't stop the run; they **spawn new agents with generated instructions** that check,
   verify, write, and re-check until the issue converges (see §6.5). Autonomy is made safe by
   principle 5 (immutable ground truth + binding rulings) plus hard convergence bounds and a final
   audit — not by a human standing guard.

---

## 2. Three failure classes → three mechanisms

| Failure | What it looks like | Mechanism that fixes it |
|---|---|---|
| **Coherence** | Facts silently change; details get mixed; the priest becomes a creditor | Structured canon + a Canon-Consistency checker at every seam; conflicts resolve to ground truth |
| **Meaning** | Coherent but hollow; a chapter/paragraph advances nothing; motifs never pay off | Intent encoded as arc-beats + setup→payoff ledger; an Intent checker asks "does this advance a named beat / keep a promise?" |
| **Micro-truth** | Locally fluent but nonsensical; a situation doesn't make sense; words don't mean anything | A Micro-Sense checker reads each prose unit against its canon slice: are details grounded, does the situation cohere, is the language load-bearing? |

Naming them apart matters: one "make it more top-down" lever cannot move all three.

---

## 3. Filesystem layout

Authors are shared library assets; everything about one novel lives in its own folder.

```
authors/
  <author_id>/                 # e.g. duerrenmatt/  — reusable across novels
    profile.yaml               # philosophy, style, patterns, critique rubric (exists today)
    nudges.md                  # how to steer toward / away; do & don't
    question_lines.md          # the recurring questions/obsessions this author "has"
    examples/                  # annotated voice samples (setup + why it works)
    impression.md              # "what it feels like to read them"
novels/
  <slug>/                      # one novel = one folder
    00_input/                  # spark, nudges, philosophical questions, user Story-DNA, author ref
    01_canon/
      story_model.json         # THE source of truth — structured, versioned, validated
      history/                 # every accepted canon version (audit trail of changes)
    02_plan/
      macro_arc.json           # acts, turning points, per-character arcs, motif schedule, tension curve
      chapters/ch03.spec.json  # per-chapter spec, elaborated just-in-time
    03_drafts/
      ch03.md                  # prose per chapter (+ scene units if used)
    04_trace/                  # every filled prompt + artifact per agent (our capture format)
    05_reports/                # checker verdicts, promote/reject decisions, repair logs
    novel.md                   # assembled output
```

---

## 4. The canon: `story_model.json`

Structured, ID-referenced, machine-checkable. **Nothing here is prose-of-record.** Sketch:

```jsonc
{
  "premise": { "spark": "...", "central_question": "...", "thesis": "...", "why_this_author": "..." },
  "characters": {
    "stettler": {                       // stable ID — never a display-name string
      "canonical_name": "Dr. Konrad Stettler",
      "aliases": ["Stettler", "der Amtsarzt"],   // known variants → no F7 fragmentation
      "role": "protagonist",
      "facts": { "profession": "Amtsarzt", "age": 58, "secret": "forged Klara Vogel's death certificate 20y ago" },
      "arc": { "want": "...", "need": "...", "flaw": "...", "trajectory": "does not change; hardens" }
    },
    "rutz": { "canonical_name": "Pfarrer Johannes Rutz", "role": "confessor",
              "facts": { "office": "village priest", "relation_to_protagonist": "old friend + private creditor" } }
  },
  "relationships": [ { "a": "berta", "b": "melchior", "type": "widow_of" } ],
  "world_facts": { "setting": "Lauenegg, Graubünden", "era": "1950s", "location:chrachen": "gorge south of village" },
  "timeline": [ { "id": "t1", "when": "20y prior", "event": "Klara Vogel dies; Stettler forges certificate" } ],
  "motifs": [
    { "id": "formula_echo", "setup_ch": 1, "payoff_ch": 3, "status": "planned",
      "desc": "the phrase 'Herzversagen, vermutlich beim Sturz' recurs identically" }
  ],
  "promises": [ { "id": "berta_question", "made_ch": 2, "kept_ch": null, "desc": "Berta's unanswered 'wie bei der Vogel?'" } ],
  "constraints": { "forbidden": ["sentimental redemption", "justice triumphs"], "language": "de" },
  "version": 7
}
```

Key properties: **stable IDs + alias lists** (kills name fragmentation, F7); **motifs/promises with
`status`** (the meaning ledger); **`history/`** so every canon change is auditable and reversible.

---

## 5. Pipeline stages (top-down, canon-centric)

Each stage **reads canon, writes canon (or plan), and is gated by the verification layer (§6).**

| # | Stage | Reads | Writes | Model |
|---|---|---|---|---|
| 0 | **Author model** | `authors/<id>/*` | in-memory author object (obsessions, question-lines, signatures) | — |
| 1 | **Conception** | input × author model | `canon.premise` (generate a few candidate "stories this author would tell"; pick/merge) | Opus |
| 2 | **World & cast → canon** | premise, input, author | `canon.characters/relationships/world_facts/timeline/constraints` — **structured, validated** | Sonnet |
| 3 | **Macro-arc** | full canon | `02_plan/macro_arc.json` — acts, turning points, per-character arc beats, **motif/promise schedule**, tension curve (all by ID) | Sonnet |
| 4 | **Chapter spec (JIT)** | full canon + macro_arc | `chapters/chNN.spec.json` — purpose, arc-beats-to-advance (IDs), setups/payoffs (IDs), entry/exit state, POV | Sonnet |
| 5 | **Prose** | chapter spec + **full canon slice** | `03_drafts/chNN.md` | Opus |
| 6 | **Reconcile** | draft + canon | extract new facts → validate → **promote or flag**; update motif/promise status | Sonnet |

Conception (1) and world/cast (2) **replace** the v1 prose-based topic/thesis/character phases: same
thinking, but the *output is canon*, not prose to be re-parsed. This is the single change that
removes the F6/F10 cascade at the root.

---

## 6. The verification & repair layer (the "roving fresh agents")

This is the heart of your ask. At **every seam**, one or more **fresh-context** checkers read the new
unit against the relevant canon slice with a sharp rubric. They do not generate; they judge and,
if needed, trigger repair.

### Checker types

| Checker | Question it answers | Fires on |
|---|---|---|
| **Canon-Consistency** | Does this unit contradict any canonical fact/relationship/timeline? (structured diff) | every stage output |
| **Intent / Meaning** | Does this unit advance the arc-beats / keep the promises it was *assigned*? Does it earn its place? | plan units (3,4) and prose (5) |
| **Micro-Sense** | Read paragraph-by-paragraph: are details grounded in canon, does the situation cohere, is the language load-bearing (not filler/hallucination)? | prose only (5) |
| **Author-Voice** | Is this the author's voice + within `constraints.forbidden`? | prose only (5) |

### Triggers — designed to avoid the F8 failure

- **Not** a single weighted-average threshold. Each checker returns a **verdict per issue**, and the
  loop fires repair when **any** checker raises a `blocking` issue — regardless of a global "score."
- Checkers run on the **smallest meaningful unit** (a paragraph/scene for Micro-Sense, the chapter
  for Intent, the whole diff for Canon-Consistency) so a problem is localized, not averaged away.
- Cheap checkers first (Canon-Consistency is largely structural/deterministic), expensive LLM
  checkers only on what passes — reclaims the F3 cost.

### Instructions — what each checker is handed

Every checker is a **fresh agent** (zero generation context) given: the unit, the **exact canon
slice** it must respect, its rubric, and an authority to return:
`PASS` · `REVISE {issues:[{unit, kind, severity, canon_ref, fix_hint}]}` · `ESCALATE {conflict}`.

### Repair

- `REVISE` → a repair agent gets the issues + canon + unit, fixes **only** the flagged spans, re-checks
  (bounded to N iterations). Repair is grounded in canon, so it cannot invent bridging facts.

This is v1's critic/guardian, re-conceived: **many small, canon-armed, fresh readers with teeth**,
instead of one averaged score and a bible that ratchets in whatever the prose said.

### 6.5 Autonomous escalation & self-adjudication (no human pause)

`ESCALATE` fires when a conflict can't be fixed locally: a unit contradicts canon, the canon looks
internally inconsistent, or an assigned beat is unsatisfiable. Instead of pausing, the orchestrator
**self-directs**:

1. **Adjudicator agent** (fresh) is spawned with: the conflict, the **immutable ground truth** (brief +
   locked Phase-2 canon), and the decision log. It issues exactly one **binding ruling**:
   - *Correct the unit to canon* (the usual case), or
   - *Amend the canon* — allowed **only** if the canon itself violates the immutable ground truth
     (mutations to locked ground truth are forbidden), or
   - *Spawn a specialist* — emit a new sub-task + generated instructions for a fresh agent
     (e.g. "timeline underspecified around event t7 — run a timeline-repair agent with these rules").
2. The ruling is appended to an **immutable decision log** (`05_reports/decisions.jsonl`) and becomes
   binding: the same conflict can never be re-opened, which guarantees **convergence** (no oscillation).
3. The spawned work runs the normal write→check cycle; if *it* escalates, it inherits the decision log,
   so each round strictly reduces open conflicts.

**Safety rails that make unattended operation safe:**
- **Immutable ground truth**: the brief and the Phase-2 canon are frozen at creation; nothing
  downstream may edit them — only read and be checked against them.
- **Convergence bounds**: per-unit repair iterations and per-run escalation depth are capped; on cap,
  the unit is quarantined (flagged in `05_reports/`, excluded from `novel.md`) rather than shipped broken.
- **Final Auditor pass**: after assembly, one whole-book fresh agent re-verifies coherence + every
  promise `kept` + no quarantined units — the last gate before the novel is declared done.
- **Full trace**: every prompt, artifact, checker verdict, and ruling is on disk (`04_trace/`,
  `05_reports/`), so the surprise is *auditable after the fact* even though no human watched it happen.

---

## 7. How macro intent is carried into micro (the seam)

The specific machinery that keeps a paragraph tied to the whole:

1. **Down:** the prose call for chapter N is generated from `chNN.spec.json`, which names — by ID —
   the arc beats to advance, the setups to plant / payoffs to deliver, and the entry/exit canonical
   state, **plus the full canon slice** for everything in scene. Intent is explicit, not implied.
2. **Check:** Micro-Sense verifies each paragraph is grounded + coherent + meaningful; Intent verifies
   the assigned beats/promises were actually hit.
3. **Up (feedback):** if the writer *couldn't* hit an assigned beat, that is a signal the **plan is
   wrong**, not a silent miss — it kicks back to Stage 4/3 to revise the plan (and canon if needed).
   Plan and draft co-evolve under validation, instead of the draft silently diverging from the plan.

This two-way loop is what a pure "freeze the outline then write" waterfall lacks — and it's why the
design is top-down *control* with bottom-up *enrichment under validation*, not a one-shot cascade.

---

## 8. Mapping to current code

| v1 element | v2 disposition |
|---|---|
| `topic/thesis/character` agents (prose out) | **Rewrite** to emit structured canon (Stages 1–2) |
| `story_architecture` agent | Keep concept → Stage 3, output `macro_arc.json` (IDs) |
| `chapter_blueprint` loop (`raw_blueprint[:800]`) | **Rewrite** to Stage 4 JIT spec grounded in full canon (kills F5) |
| `ProseGenerationLoop` (reason→write→critique→revise) | Keep the loop shape; swap the gate for the §6 checker layer; ground the writer in full canon |
| `phase7_consistency` guardian + `story_bible.py` | **Rewrite** as the Reconcile step (Stage 6) writing structured canon with stable IDs/aliases (kills F7/F10) |
| double LLM extract call in planning agents | **Delete** — native structured output in one call (kills F3) |
| SQLAlchemy bible tables | Back the canon with the DB *or* the `01_canon/` files; TBD in Phase 1 |

Nothing about the hexagonal architecture or the FastAPI/WebSocket shell needs to change; this is a
rework of the agent layer + the state substrate, which is exactly where v1 intended the logic to live.

---

## 9. Phased build plan

- **P0 — Skeleton & authors.** Create `authors/<id>/` (migrate the two profiles + add nudges/
  question_lines/examples) and the `novels/<slug>/` layout. Move the existing capture in as the first
  `novels/der-chrachen/` for reference. *(Low risk, unblocks everything.)*
- **P1 — Canon core.** Define `story_model.json` schema + a validation library (structural checks:
  referential integrity, alias resolution, timeline sanity). This is the spine everything hangs on.
- **P2 — Conception + structured world/cast.** Stages 1–2 emit canon (replace prose topic/thesis/
  character). Author-as-driver conception. Gate with Canon-Consistency.
- **P3 — Macro-arc + JIT chapter specs.** Stages 3–4 with the motif/promise ledger; Intent checker.
- **P4 — Grounded prose + Reconcile.** Stage 5 grounded in full canon; Stage 6 fact-extraction →
  validate → promote/flag with stable IDs.
- **P5 — Verification/repair layer.** The §6 checkers (Micro-Sense, Intent, Voice) + triggers + repair
  + escalate-to-ground-truth. Tune triggers/instructions here.
- **P6 — Assembly + eval.** Re-run *Der Chrachen* end-to-end; compare coherence/meaning/micro-truth
  against the v1 capture to prove the redesign.

Each phase is independently testable and leaves the system runnable.

---

## 10. Decisions locked & remaining risks

**Locked (creator decisions):**
- **D1 — Canon storage:** files in `01_canon/` are the source of truth (inspectable, versionable,
  matches the folder vision); DB is a read index only.
- **D2 — Schema rigidity:** hard/validated schema for *entities, facts, timeline, relationships*;
  free-text (LLM-checked, not schema-checked) for *intent, atmosphere, voice*.
- **D3 — Autonomy:** fully autonomous. Human input is a light **front-door brief** only; no approval
  pauses; escalations self-adjudicate (§6.5); the novel is meant to surprise the creator. v1's
  `APPROVAL_PHASES` gates are **off by default**. The creator reviews the finished novel + trace, not
  the intermediate steps.

**Remaining risks:**
1. **Autonomy amplifies a wrong ruling** — the core danger. Contained by: immutable ground truth,
   binding/logged rulings (no oscillation), convergence caps with quarantine, and the Final Auditor.
   Residual risk: a *plausible-but-flat* story the auditor rates "coherent" but the creator finds dull —
   autonomy can't fully guarantee *taste*. Mitigation: the brief's question-lines + author obsessions
   are treated as immutable intent the Intent-checker enforces.
2. **Cost:** more checker calls = more tokens. Offset by deleting the F3 double-call, running cheap
   structural checks before LLM checks, and parallelizing checkers over small units. Net vs v1 = TBD;
   measure against the per-book economics question.
3. **Where "paragraph arcs" stop:** scene-level planning by default; paragraph granularity lives in
   Micro-Sense *checking*, not paragraph *pre-planning* (avoids a novel-length outline).
4. **Convergence tuning:** the caps in §6.5 need empirical tuning — too tight quarantines good units,
   too loose burns tokens. Calibrate during P5.

---

### One-line summary
Make a **structured canon the single source of truth**, elaborate **top-down just-in-time** with every
generation **grounded in the full canon**, and guard every seam with **fresh, canon-armed checkers for
coherence, meaning, and micro-sense** that repair toward ground truth — never toward a mutable bible.
