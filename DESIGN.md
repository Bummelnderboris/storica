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
   never re-parsed as truth — facts are extracted from prose and *validated into* canon. **This binds
   humans too:** canon is authored from the brief and from validated upstream canon, never
   reconstructed by reading prose after the fact (§4.1).
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
| **Vitality** | Correct, coherent, on-plan — and dead. Executes the outline; explains its own gestures; could have been written without imagining the scene | Generate-and-select on prose (§5) plus a Vitality checker whose polarity is inverted: it fails a unit for being *safe*, and its fixes are cuts |

Naming them apart matters: one "make it more top-down" lever cannot move any of them.

**On the fourth.** It was originally filed under residual risks (§10) rather than as a failure class,
and that was a mistake worth stating plainly. Every other checker here is a **conformance** check, so
a chapter that matches canon, hits its beats and sounds like the author passes the entire gate no
matter how inert it is. Worse, the machinery *manufactures* that chapter: every repair iteration
moves prose toward the rubric and away from whatever was surprising in it, so the system's natural
product is competent, correct and lifeless. Meanwhile v1's real output was already good
sentence-by-sentence — fluency was never what it lacked — and the stated goal is a book that
surprises its creator, which nothing else in the pipeline optimises for and several things suppress.

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
    00_input/brief.yaml        # author_id, spark, thoughts, question_lines, nudges, forbidden, language, chapter_count
    01_canon/
      story_model.json         # THE source of truth — structured, versioned, validated
      history/                 # every accepted canon version (audit trail of changes)
    02_plan/
      macro_arc.json           # acts, turning points, per-character arcs, motif schedule, tension curve
      chapters/ch03.spec.json  # per-chapter spec, elaborated just-in-time
    03_drafts/
      ch03.md                  # prose per chapter (+ scene units if used)
    04_trace/                  # every filled prompt + artifact per agent (our capture format)
    05_reports/                # decisions.jsonl, quarantine.jsonl, state.json
    06_session/                # replay driver only: request/response cache
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
    // NOTE: this entry once read "old friend + private creditor" — which is exactly the F11
    // bridging fact, the invention that let a contradiction survive as elaborated false canon.
    // It got here because this example was written by reading the v1 *output*. See §4.1.
    "rutz": { "canonical_name": "Pfarrer Johannes Rutz", "role": "confessor",
              "facts": { "office": "village priest", "relation_to_protagonist": "old friend" } }
  },
  "relationships": [ { "a": "berta", "b": "melchior", "type": "widow_of" } ],
  "world_facts": { "setting": "Lauenegg, Graubünden", "era": "1950s", "location:chrachen": "gorge south of village" },
  "timeline": [ { "id": "t1", "when": "20y prior", "event": "Klara Vogel dies; Stettler forges certificate" } ],
  "knowledge": [
    { "id": "k_forgery", "fact": "Stettler forged Klara Vogel's death certificate.",
      "concerns": ["stettler", "t1"],
      "holders": [ { "character_id": "stettler", "awareness": "knows", "since": "t1" },
                   { "character_id": "berta", "awareness": "suspects", "since": "ch2" },
                   { "character_id": "marolf", "awareness": "believes_false",
                     "instead": "that Klara Vogel died of heart failure" } ] }
  ],
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
`status`** (the meaning ledger); **`knowledge`** (below); **`history/`** so every canon change is
auditable and reversible.

### 4.1 Knowledge state — who knows what, when

`facts` say what is true. `knowledge` says **who has access to it**, and in a story built on a
concealed secret that distribution *is* the plot: the tension in a scene is the gap between what the
reader knows, what the POV character knows, and what the person across the table knows.

Each item carries a fact and a list of holders, each `knows` / `suspects` / `unaware` /
`believes_false` (with what they hold instead), and since when. **Anyone not listed is unaware** —
silence is never permission. The canon slice renders this per character *including their ignorance*,
because an omission reads as "unspecified", and unspecified is what gets leaked into the prose.

Without this, nothing stops a writer having a character allude to something they cannot know, and no
checker can catch it — the classic failure of machine-written fiction, and one v1 had no vocabulary
for. `StateFact` gestured at it (`"stettler:knows"` as free text) but nothing validated or enforced it.

**Ground-truth rule (added after the calibration run).** Canon may be authored **only** from the
brief and from validated upstream canon — never from prose, and never reconstructed after the fact.
Principle 1 says prose is never re-parsed as truth, but said nothing about *humans* doing it, and the
gap bit: the reference canon in `novels/der-chrachen/01_canon/` was written by reading the corrupted
v1 output and silently absorbed the F11 bridging fact, as did the example above. Ground truth derived
from corrupted prose inherits the corruption. See `calibration/FINDINGS.md` C1.

---

## 5. Pipeline stages (top-down, canon-centric)

Each stage **reads canon, writes canon (or plan), and is gated by the verification layer (§6).**

| # | Stage | Reads | Writes | Model |
|---|---|---|---|---|
| 0 | **Author model** | `authors/<id>/*` | in-memory author object (obsessions, question-lines, signatures) | — |
| 1 | **Conception** | input × author model | `canon.premise` (generate a few candidate "stories this author would tell"; pick/merge) | Opus |
| 2 | **World & cast → canon** | premise, input, author | `canon.characters/relationships/world_facts/timeline/constraints` — **structured, validated**; the brief outranks the model on `language` and `chapter_count` | Sonnet |
| 3 | **Macro-arc** | full canon | `02_plan/macro_arc.json` — acts, turning points, per-character arc beats, **motif/promise schedule**, tension curve (all by ID) | Sonnet |
| 4 | **Chapter spec (JIT)** | full canon + macro_arc | `chapters/chNN.spec.json` — purpose, arc-beats-to-advance (IDs), setups/payoffs (IDs), entry/exit state, POV | Sonnet |
| 5 | **Prose** | chapter spec + **full canon slice** + the author's craft + the chapter so far | `03_drafts/chNN.md` — *k* drafts per scene, then select (§5.1) | Opus |
| 6 | **Reconcile** | draft + canon | extract new facts → validate → **promote or flag**; update motif/promise status | Sonnet |

Conception (1) and world/cast (2) **replace** the v1 prose-based topic/thesis/character phases: same
thinking, but the *output is canon*, not prose to be re-parsed. This is the single change that
removes the F6/F10 cascade at the root.

### 5.1 Selection, not just repair

Stage 5 draws **k independent drafts of each scene from the identical prompt**, then one cheap call
picks the most alive; only the winner enters the checker/repair loop.

The reasoning: repair is a regression-to-the-mean engine. Each iteration moves a draft toward the
rubric, and the rubric is all it can move toward, so variance is spent sanding one draft down.
Selection spends the same variance *choosing* instead, which preserves the spread rather than
collapsing it. Conception already worked this way (`n_candidates=3` → `ConceptionChoice`); prose,
which carries the actual book, did not.

Cost shape matters or this gets switched off: k drafts cost **k generate calls plus one selection
call**, never k full checker passes. Deterministic stub-filtering runs before the selector, so no
judgement is ever spent comparing against an empty draft; if every candidate is a stub, the last
one goes straight into the repair loop rather than costing another generate call. The prompts are identical across drafts on
purpose — steering each toward "a darker version" would make it a choice between instructions rather
than between imaginations.

Repair is kept for what it is genuinely good at: factual contradiction, where conformance *is* the
goal. `--prose-candidates 1` disables selection for a cheap run.

### 5.2 What the writer is given, and what it may invent

The writer is the one agent the book's quality actually depends on, and for a long time it was the
least informed agent in the building. Three things it now gets that it did not:

- **The author's craft, not only the no-list** (`AuthorModel.writer_block()`): sentence patterns,
  register, dialogue, openings and endings, register samples, and the impression — the material the
  voice and vitality readers judge it against. It used to get ~200 words of steer-toward/away while
  its judges were shown more of the author than it was.
- **The whole chapter so far.** Scene *n* sees every earlier scene of its chapter in full, not an
  800-character tail — without it scene 3 could not know what was said in scene 1. The previous
  chapter still arrives as a tail plus reconciled canon.
- **A private imagining step** before drafting: where everyone is, what each wants from the other and
  will not say, the one particular thing the reader will remember, where exactly the turn lands. The
  answers are not written down; the prose carries them. (On the API path Opus 5 thinks by default,
  so this is where that thinking is pointed.)

And one rule, shared byte-for-byte with the micro-sense reader (`canon/invention.py`): **what prose
may invent.** Texture, minor specifics (a date, an hour, a street, a file number), procedure and
unnamed walk-ons are the writer's to imagine, and reconcile records them into canon so later chapters
are held to them. Named people, relationships, who knows what, and the story's open questions are
not. The old rule — "invent texture, never a fact about a person, a place, a time or an event" —
drew no line, and the reader drew a stricter one than the writer was given (calibration C7).

---

## 6. The verification & repair layer (the "roving fresh agents")

This is the heart of your ask. At **every seam**, one or more **fresh-context** checkers read the new
unit against the relevant canon slice with a sharp rubric. They do not generate; they judge and,
if needed, trigger repair.

### Checker types

| Checker | Question it answers | Fires on |
|---|---|---|
| **Canon-Consistency** | Does this unit contradict any canonical fact/relationship/timeline? (structured diff) | prose (5); plan units (3,4) are gated by schema validation plus Intent |
| **Intent / Meaning** | Does this unit advance the arc-beats / keep the promises it was *assigned*? Does it earn its place? | plan units (3,4) and the **assembled chapter** (5) — advisory on prose until calibrated |
| **Micro-Sense** | Read paragraph-by-paragraph: does any detail breach the invention policy, does the situation cohere, is the language load-bearing? | prose scenes (5) |
| **Author-Voice** | Is this the author's voice + within `constraints.forbidden`? | prose scenes (5) |
| **Vitality** | Is this *alive*? Does it explain its own gestures, announce its interiority, restate the outline? Would anyone be surprised by it? | prose scenes (5) |
| **Repair verifier** | Were the pinned issues resolved, and did the edit break anything where it edited? | after each prose repair (§6.2) |

**Vitality is deliberately handed a thin slice** — premise and constraints, no character facts, no
timeline. Given the full canon it will drift into checking consistency, because that is the more
concrete and more answerable job, and then nobody is doing the one it exists for. Its fix hints are
required to be **subtractive** ("cut the sentence beginning…"), which is what makes it safe to pair
with the repair loop's minimal-edit contract: deleting the sentence that explains the gesture is a
small, local, non-inventing edit, and it is usually the whole fix. It never escalates — there is no
upstream conflict that makes prose dull.

**Vitality gates on density, and that is not a relapse into v1's score.** Measured on a matched pair
— one chapter as written, and the same chapter with the anti-patterns inserted (`FINDINGS.md` C6):

| | blocking issues / 1000 words |
|---|---|
| as written | 2.5, 2.5, 5.1 |
| flattened | 18.1, 18.1, 15.7 |

Threefold separation, and the flagged spans are exactly the inserted ones — the signal works. But
*both* returned `revise` in every draw, because good prose also has two or three places a sharp
reader would cut. Under "any blocking issue → repair" this checker fires on **every chapter ever
written**, sending the whole book through the step that flattens prose: it would have manufactured
the failure it exists to prevent. So it blocks at **≥ 8 issues per 1000 words and ≥ 3 issues**, with
sub-threshold findings demoted to warnings rather than dropped.

Nothing is averaged and nothing is scored; every issue stays located and independently actionable.
The count answers only *how much* — a chapter with a few soft spots, or a chapter that is dead
throughout — and degree is what a count is for. The threshold is fitted to n=3 on one chapter of one
restrained author, which is where the gap between *withholding* and *flat* is narrowest; expect to
retune it.

### Lens, trigger, authority

The table above is a list of **lenses**, and the lens is the part worth writing carefully: the
questions a reader asks and the stance it takes ("you did not write this; canon is truth"). It is not
the same decision as *where* the reader fires, nor as *what it may do* about what it finds. Welding
all three into one class had two costs: a lens could only ever be used at the seam it was written
for, and its power was invisible — you had to read the class to find out whether its verdict could
stop a book.

They are three knobs now, bound by one `ReaderSpec` row in `src/storica/checkers/registry.py`:

- **lens** — the checker class.
- **trigger** — `Scope.UNIT` (every scene *and* the assembled chapter), `Scope.SCENE`,
  `Scope.CHAPTER`; plus whether the reader is sampled *k* times (§6.1).
- **authority** — `ESCALATE` (may block a unit and may reach the adjudicator), `BLOCK` (may block,
  but an escalation is capped into a blocking issue, because a reader that has not been shown the
  immutable ground truth should not be able to stop the run), `ADVISE` (findings are demoted to
  warnings and recorded — never blocks, never escalates).

The shipped gate, in order, with the reason each row is set the way it is:

| Reader | Trigger | Authority | Why |
|---|---|---|---|
| **canon_consistency** | every unit, sampled | escalate | measured (C4); reads the chapter too, because a contradiction *between* scenes exists only there |
| **micro_sense** | scenes only | escalate | paragraph-local by definition; shares the writer's invention policy (C7); calibrated in C8 |
| **voice** | scenes only | escalate | judged sentence by sentence; calibrated in C8 |
| **vitality** | scenes only | escalate | gates on issue *density*, not presence (C6) |
| **intent** | assembled chapters only | **advise** | beats are a chapter-scale question; uncalibrated, so it records and does not block |

Why the three local readers no longer read the assembled chapter: a scene pass has already asked
their questions of every sentence in it, so the chapter pass bought nothing but a second fresh draw
on the same text — and a fresh draw re-rolls the verdict (C7). A chapter could pass every scene and
then fail on a sentence it had already passed. The chapter-scale questions belong to the two readers
that still fire there.

Two consequences. A lens is reusable at any seam, so Intent is now one lens reading the arc, each
chapter spec, **and** the prose those plans produced — which closes the gap that no reader ever
judged whether a chapter *delivered* its assigned beats; before, that was only inspected after the
fact by reconcile's ledger extraction. And scope is a cost lever as well as a policy one: an
out-of-scope unit costs no model call at all, so the gate carries five readers while adding roughly
one call per chapter-level pass rather than one per scene.

### Triggers — designed to avoid the F8 failure

- **Not** a single weighted-average threshold. Each checker returns a **verdict per issue**, and the
  loop fires repair when **any** checker raises a `blocking` issue — regardless of a global "score."
- Checkers run on the **smallest meaningful unit** (a paragraph/scene for Micro-Sense, the chapter
  for Intent, the whole diff for Canon-Consistency) so a problem is localized, not averaged away.
- Cheap checkers first (Canon-Consistency is largely structural/deterministic), expensive LLM
  checkers only on what passes — reclaims the F3 cost. On prose this is a short-circuit: if
  canon-consistency blocks, micro-sense, voice and vitality are not run on that draft; they read
  the repaired text.

### 6.1 Sampling: majority decides, union reports

A single LLM verdict is not a stable gate. Measured on the same prompt drawn five times
(`calibration/FINDINGS.md` C4): the chapter with five planted contradictions returned `revise` in
**5/5** draws; the clean control returned a blocking issue in **1/5**. The checker is decisive about
real breakage and noisy about clean text.

That asymmetry rules out the intuitive aggregation:

| rule | blocks clean text | catches broken text |
|---|---|---|
| single draw | 20% | reliably |
| union over k=3 ("any draw blocks") | **49%** | reliably |
| **majority over k=3** | **10%** | reliably |

Union-blocking multiplies the noise it is meant to average out, and every false block costs a trip
through the repair loop — the step that flattens prose (§5.1). Majority beats even a single draw on
false positives and loses nothing on recall, because genuinely broken text blocks in every draw.

**The rule: majority decides, union reports.** Once a majority judges the unit broken, the repair
agent receives every issue *any* draw found — a real contradiction spotted by one careful reader is
still real, and this is what recovers the error a single draw missed 1 time in 5. Escalation needs
the same majority: a binding ruling is too expensive to trigger on one alarmed reader.

Applied to canon-consistency only (`--checker-samples 3`, `1` to disable). Sampling every checker
would triple the gate for asymmetries nobody has measured — micro-sense, voice and vitality remain
uncalibrated, and vitality is the one most likely to be generous, since LLM judges reward fluency and
fluency is exactly what an inert chapter has.

**A pass is still weaker evidence than it looks.** The final auditor should not treat per-chapter
passes as settled.

### Instructions — what each checker is handed

Every checker is a **fresh agent** (zero generation context) given: the unit, the **exact canon
slice** it must respect, its rubric, and an authority to return:
`PASS` · `REVISE {issues:[{unit, kind, severity, canon_ref, fix_hint}]}` · `ESCALATE {conflict}`.

### Repair

- `REVISE` → a repair agent gets the issues + canon + unit, fixes **only** the flagged spans, and the
  fix is verified (§6.2), bounded to N rounds (`--max-repairs`, default 3). Repair is grounded in
  canon, so it cannot invent bridging facts.

### 6.2 Convergence: read once, pin, verify

A unit is read by the full gate **exactly once**. Its blocking issues are **pinned**, and every repair
after that is judged by one fresh **repair verifier** against the pins alone: was each resolved, and
did the edit itself break something — in the passages it changed, and only there (the verifier is
shown a paragraph diff, never the unchanged text).

The loop used to re-run the whole gate after every repair, which sounds rigorous and is the
opposite: a fresh reader is a new draw, a new draw finds new issues, and the target moved every
round. P6's chapter 1 died of exactly that (C7) — three reads of one scene, three different blocking
questions, none asked twice. With pins, the open list can only shrink or be replaced by damage the
repair demonstrably did, so a budget converges; and a round costs two calls (repair + verify)
instead of five to seven.

The fallback is honest: if a repair rewrote most of the unit instead of editing spans, there is no
small diff to verify, and the new text is read by the full gate again. And the short-circuit keeps its
promise: readers canon-consistency's block skipped read the repaired text once the pins clear, and
what they find is pinned and verified in turn. (Missing in the first cut of this loop, and caught
live in P6's chapter 2, scene 1: the scene would have passed unread by micro-sense, voice and
vitality.) Warnings from the one full
read are carried to the result unchanged and never drive a repair.

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
   binding: the same conflict can never be re-opened, and every earlier ruling rides into each later
   re-attempt of the chapter, which guarantees **convergence** (no oscillation). Rulings act: at
   reconcile, *correct the unit* triggers one grounded repair pass on the saved draft, bound by the
   ruling's instruction; *amend canon* quarantines the chapter and commits nothing to canon.
3. The spawned work runs the normal write→check cycle; if *it* escalates, it inherits the decision log,
   so each round strictly reduces open conflicts.

**Plans escalate by the same path.** `pipeline._bound_by_rulings` wraps the macro-arc and
chapter-spec stages exactly as `chapter.attempt_chapter` has always wrapped prose: an Intent
escalation is adjudicated, the binding ruling is logged, and the stage is re-attempted bound by it,
with guidance accumulating across rulings so a second escalation does not make the stage forget the
first. A ruling that would amend canon stops the stage rather than applying it — a planning conflict
is exactly where the v1 ratchet would start. On an exhausted budget the stage raises its own
`GateFailed` so the caller can contain it: a chapter spec quarantines its chapter, the macro arc
stops the run. Until this existed both escaped as tracebacks, contradicting this section's central
claim that no escalation is a pause.

**Safety rails that make unattended operation safe:**
- **Immutable ground truth**: the brief and the Phase-2 canon are frozen at creation; nothing
  downstream may edit them — only read and be checked against them.
- **Convergence bounds**: per-unit repair iterations and per-run escalation depth are capped; on cap,
  the unit is quarantined (flagged in `05_reports/`, excluded from `novel.md`) rather than shipped
  broken. A quarantine is skipped on every later run until released with `--retry-quarantined`,
  which appends a release record and re-attempts the chapter, usually with a larger repair budget.
  A chapter spec or reconcile that fails its gate is contained the same way; only canon and the
  macro arc, which have no chapter to quarantine into, stop the run.
- **Final Auditor pass**: after assembly, one whole-book fresh agent re-verifies coherence + every
  promise `kept` + no quarantined units — the last gate before the novel is declared done. A promise
  the arc scheduled as deliberately unresolved (`kept_ch: 0`) is a warning, not a block; one planned
  for a chapter and never kept still blocks.
- **Full trace**: every prompt, artifact, checker verdict, and ruling is on disk (`04_trace/`,
  `05_reports/`), so the surprise is *auditable after the fact* even though no human watched it happen.

### 6.6 Acting on the final audit

The final auditor is the only reader that sees the whole book, so it is the only one that can find a
contradiction *between* chapters — each clean on its own. Its `revise` used to be reported and
nothing more; P6's first complete book ended there, with eight such findings. Now each blocking
finding is **routed to one chapter** (`audit_repair.py`) and repaired under the ordinary contract,
checked by the repair verifier against the finding and a diff; then a fresh audit reads the book
again (`--audit-repairs`, default 2 rounds). When the audit *escalates* a canon-side conflict,
the adjudicator rules first; a `correct_the_unit` ruling becomes one more finding for the same repair
round, and an `amend_canon` ruling stops the loop for a human. (In P6, round 1 took the book from 8
blocking findings to 3 plus one escalation, whose ruling was at first recorded and acted on by
nothing — the reason this branch exists.)

Exactly one side of a contradiction moves: the chapter the fix hint names, when it names one;
otherwise the **later** chapter, because the earlier one was reconciled into canon before the later
one was written against it. A repair that rewrites a chapter instead of editing it is rejected — the
chapter already passed its full gate, and a rewrite would put unread text into the book at the last
step. Rounds are recorded in `05_reports/state.json`, so a replay-driven run that pauses mid-round
replays the first audit against the book it originally read.

Limitation: the repaired chapters are not re-reconciled. The edits are corrections toward what canon
already holds, so reconcile would have nothing to promote; if that assumption fails, the second
audit is where it shows.

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
4. **Up (enrichment):** what the prose legitimately invented (§5.2) — a date, a place, a procedure,
   a shift in who knows what — is extracted by reconcile and promoted into canon, placed in story
   order, so the next chapter is written against it. The extractor judges whether a fact is new, a
   restatement or a contradiction, because only a reader can tell a paraphrase from a change.

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
  against the v1 capture to prove the redesign. **Underway** in `novels/der-chrachen-v2/`: canon,
  macro arc and the chapter 1 spec passed; chapter 1 was quarantined when scene 3 exhausted two
  repairs on a micro-sense issue — an unglossed date. The trace showed the cause was the gate, not
  the prose (C7): each full re-read re-rolled the question, and the reader held the writer to a
  stricter invention rule than the writer had been given. Fixed by §5.2 and §6.2; chapter 1 is
  released and re-attempted under the new gate.

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
   *(The "plausible-but-flat story" that used to sit here has been promoted out of the risk list: it
   is failure class four in §2, with selection and the Vitality checker against it.)*
1b. ~~**The gate is non-deterministic.**~~ Measured and handled: majority-of-3 sampling (§6.1),
   and repair verified against pinned issues rather than re-rolled (§6.2). Micro-sense and voice
   were floor-tested in C8 on the same clean control as C3/C6. Residual: the repair verifier is
   itself a single unsampled judgement; intent on prose is unmeasured and so only advises; C8 is
   n=3 on one chapter of one author.
1c. **Ground truth can be corrupted by a human.** Already happened once, in the reference canon and
   in this document's own §4 example. The rule in §4.1 is the mitigation; nothing enforces it
   mechanically yet.
2. **Cost:** more checker calls = more tokens. Offset by deleting the F3 double-call, running cheap
   structural checks before LLM checks, and parallelizing checkers over small units. Net vs v1 = TBD;
   measure against the per-book economics question.
3. **Where "paragraph arcs" stop:** scene-level planning by default; paragraph granularity lives in
   Micro-Sense *checking*, not paragraph *pre-planning* (avoids a novel-length outline).
4. ~~**Convergence tuning.**~~ The loop now converges by construction (§6.2); the cap (default 3
   rounds, two calls each) bounds cost rather than papering over a moving target. Still worth
   measuring on a finished book: how many rounds units actually need.
5. ~~**Reconcile is paraphrase-sensitive.**~~ The extractor now classifies each fact as new,
   restatement or contradiction (`FactRelation`); a restatement is recorded (`RESTATED`) and never
   adjudicated. Code keeps the conservative backstop: a fact called new whose key canon already
   fills differently is still a contradiction.
6. ~~**Retrospective events land last.**~~ Each extracted event names the canon event it follows in
   story time (`after_event_id`) and is inserted there; `order` is renumbered.
7. ~~**Knowledge is write-once.**~~ Reconcile extracts knowledge shifts the page delivers and
   records them `since: chN`. Knowledge only moves forward: a regression, or a shift the plan
   scheduled for a later chapter arriving early, is a contradiction for adjudication. The slice now
   renders knowledge *as of the chapter being written*, so a shift scheduled for ch2 reads as the
   ignorance it still is in ch1 — before this, chapter 1's writer was shown "suspects (since ch2)".
8. **There is no separate specialist agent.** A `spawn_specialist` ruling emits a real sub-task, and
   `reports.binding_guidance()` carries it — with the ruling's instruction — into the unit's own
   re-attempt, in the chapter loop and the planning loop alike. For a long time the sub-task was
   validated, logged and then dropped, so this is the fix; but the work still happens inside the
   retry of the unit that failed, not in the dedicated fresh agent §6.5 describes. Weaker, and worth
   closing.
9. **Canon grows with the prose.** The invention policy (§5.2) means reconcile promotes more
   specifics, and every slice carries them. For three chapters this is noise; for thirty the slice
   will need a relevance filter (world facts are currently rendered in full to every unit).
10. **Refusals stop the run.** On the API path a `stop_reason: "refusal"` raises and ends the run
   (exit 1). Opus 5 supports server-side refusal fallbacks; not wired, because the live path has
   never run and a fallback to a different model would change what the run measures.

---

### One-line summary
Make a **structured canon the single source of truth**, elaborate **top-down just-in-time** with every
generation **grounded in the full canon**, and guard every seam with **fresh, canon-armed checkers for
coherence, meaning, and micro-sense** that repair toward ground truth — never toward a mutable bible.
