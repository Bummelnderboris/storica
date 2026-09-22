# Storica

*Where the unwritten waits.*

Storica writes novels. You give it a light brief — a spark, a few questions you want the book to
chase, an author whose obsessions should shape it — and it plans, drafts, checks, repairs and
assembles a whole book unattended. There are no approval prompts. The result is meant to surprise
you, and every decision it made along the way is on disk afterwards so you can find out why.

---

## Status: read this first

The repository holds two generations of Storica. **Only one of them is live.**

| | What it is | Where | State |
|---|---|---|---|
| **v2** | A canon-centric pipeline, run from the CLI | `src/storica/` | **Current.** 367 tests passing. Never yet run end-to-end against the real API |
| **v1** | A FastAPI + React web app with an 8-phase agent pipeline | `legacy/` | **Archived.** Superseded by v2 — see [`legacy/README.md`](legacy/README.md) for why |

If you are looking for "the pipeline", it is v2. The web app in `legacy/` ran, but its design had a
structural flaw that could not be tuned away ([the story](#how-we-got-here)).

**The honest gap:** every stage, checker and repair loop is implemented and unit-tested, but no book
has yet been produced by v2 from brief to `novel.md`. That run is the next thing to do.

---

## Quick start

No API key needed. The replay driver runs the *real* prompts and stops whenever it needs an answer
you haven't recorded yet:

```bash
python -m venv .venv && .venv/bin/python -m pip install -e ".[dev]"
source .venv/bin/activate

storica new novels/my-novel --author duerrenmatt \
  --spark "A retired judge secretly re-tries a case from his own past." \
  --language de --chapters 6

# edit novels/my-novel/00_input/brief.yaml — this is the only thing you write

storica run novels/my-novel
storica status novels/my-novel
```

To run it for real, put `ANTHROPIC_API_KEY` in `.env` (see `.env.example`) and add `--driver anthropic`.

The three commands are all there are:

| Command | Does |
|---|---|
| `new <dir> --author <id>` | Creates the folder skeleton and `00_input/brief.yaml` |
| `run <dir>` | Runs the pipeline. **Resumable** — every stage skips itself if its artifact already exists, so a run that dies at chapter 7 resumes at chapter 7 |
| `status <dir>` | Canon version, chapters specced/drafted, anything quarantined |

Useful flags: `--no-checkers` (structure only, no LLM judgement — fast and cheap), `--no-audit`
(skip the whole-book final read), `--audit-repairs N` (rounds of acting on a `revise` from the final
audit, default 2), `--max-repairs N` (default 3), `--retry-quarantined` (release
every quarantined chapter and attempt it again — without it, a quarantined chapter is skipped on
every later run).

Exit codes: `0` done, `1` a stage failed its gate or the model refused, `2` a call needs an answer
(replay driver), `3` a recorded answer was malformed.

---

## How Storica works

### The one idea

**Canon is the substrate; prose is only an output.**

A single structured, versioned `story_model.json` is the source of truth — characters with stable
IDs and alias lists, world facts, a timeline, and a ledger of motifs and promises with their
setup/payoff status. Every stage reads from it and writes back to it. Prose is generated *from*
canon and reconciled *into* canon, but it is never re-read as truth.

That inversion is the whole design. v1 passed prose between stages and let each one re-interpret it;
meaning leaked at every hand-off and errors became permanent. See [`DESIGN.md`](DESIGN.md) for the
full argument.

### The six stages

Each one reads canon, writes canon or plan, and is gated by the checker layer.

| # | Stage | Reads | Writes | Model |
|---|---|---|---|---|
| 1 | **Conception** | brief × author | `canon.premise` — generates several stories *this author* would tell, then picks | Opus |
| 2 | **World & cast** | premise, brief | characters, relationships, world facts, timeline, constraints | Sonnet |
| 3 | **Macro arc** | full canon | `macro_arc.json` — acts, turning points, arc beats, the motif/promise schedule | Sonnet |
| 4 | **Chapter spec** | canon + arc | `chNN.spec.json` — beats to advance, setups to plant, payoffs to deliver, entry/exit state | Sonnet |
| 5 | **Prose** | spec + **full canon slice** + the author's craft + the chapter so far | *k* drafts per scene → select the most alive → `03_drafts/chNN.md` | Opus |
| 6 | **Reconcile** | draft + canon | extracts facts from the draft, validates them, promotes or flags; updates the ledger | Sonnet |

Stage 4 runs **just in time**, one chapter at a time, immediately before that chapter is written —
so it sees everything the previous chapters established. A frozen mega-outline written up front is
itself novel-length and drifts; this avoids that.

Stage 5 **selects rather than repairs**. It draws several independent drafts of each scene from the
identical prompt and one cheap call picks the most alive; only the winner enters the checker loop.
Repair is a regression-to-the-mean engine — every iteration moves a draft toward the rubric and away
from whatever was surprising in it — so the variance is better spent choosing than sanding. Cost is
*k* generate calls plus **one** judgement, not *k* gates. Use `--prose-candidates 1` to turn it off.

The writer is told **what it may invent** — one rule, shared word for word with the micro-sense
reader ([`canon/invention.py`](src/storica/canon/invention.py)). Texture, minor specifics (a date,
an hour, a street), procedure and unnamed walk-ons are its to imagine, and reconcile records them into
canon so later chapters are held to them; named people, relationships, who knows what and the
story's open questions are not. It also gets the author's full craft (sentence patterns, register,
dialogue, register samples — not just the no-list), the whole chapter written so far, and a private
"picture the scene first" step before drafting.

### Knowledge state

Canon records not just what is true but **who knows it** — per character, `knows` / `suspects` /
`unaware` / `believes_false`, and since when. In a story built on a concealed secret that
distribution *is* the plot. Anyone unlisted is unaware, and the slice states each character's
ignorance explicitly, because an omission reads as "unspecified" and unspecified is what leaks into
the prose.

### The checkers

The writer is blind to its own drift, so it never judges its own work. At every seam a
**fresh-context** agent reads the new unit against the exact canon slice it must respect, and can
return `PASS`, `REVISE` (with located issues) or `ESCALATE`.

| Checker | Asks | Runs on |
|---|---|---|
| **Canon-consistency** | Does this contradict a canonical fact, relationship or timeline entry? | prose (plans are gated by schema validation plus Intent) |
| **Intent** | Does this advance the beats it was *assigned*? Does it keep its promises? | the arc, each chapter spec, and each assembled chapter — **advisory** on prose |
| **Micro-sense** | Paragraph by paragraph: does a detail breach the invention policy, does the situation cohere, is the language load-bearing? | prose scenes |
| **Author-voice** | Is this the author, and inside the forbidden list? | prose scenes |
| **Vitality** | Is this *alive*? Does it explain its own gestures, announce its emotions, restate the outline? | prose scenes |
| **Repair verifier** | After a repair: were the pinned issues fixed, and did the edit break anything where it edited? | each repair round |
| **Final auditor** | One fresh reader on the whole assembled book | once, at the end |

There is deliberately **no single averaged score**. v1 gated on a weighted mean of 7.0, which a
competent draft clears every time — so the gate could never fire on the thing that actually mattered.
Here any checker raising a blocking issue triggers repair, and checkers run on the smallest
meaningful unit so a problem is localised rather than averaged away. Cheap structural checks run
before expensive LLM ones.

**A unit is judged in full once; repairs are verified, not re-judged.** The blocking issues of that
one full read are pinned, and after each repair a fresh verifier checks only those pins, against a
diff of what the repair changed. Re-running every reader after every repair looked rigorous and could
not converge: each fresh read is a new draw that asks a new question, which is exactly how P6's first
chapter died (`calibration/FINDINGS.md` C7). A repair round now costs two calls, and the open list
can only shrink.

**Canon-consistency is sampled three times and blocks on a majority**, because a single LLM verdict
flags clean prose about 20% of the time. Majority decides; once blocked, repair sees the union of
everything all three draws found. See the calibration below. It also runs first and
**short-circuits**: if it blocks, micro-sense, voice and vitality are not spent on that draft — they
read the repaired text instead. When it passes, those three run concurrently, on scenes only: their
questions are local, and asking them again of the assembled chapter was a second draw on sentences
they had already passed.

**Vitality is the odd one out, on purpose.** The other four are conformance checks, so a chapter that
matches canon, hits its beats and sounds like the author passes the whole gate no matter how inert it
is — and since repair pushes prose toward the rubric, that is the chapter this pipeline naturally
produces. Vitality can only fail a unit for being *safe*, and its fixes are always cuts: the sentence
that explains the gesture, the adjective that tells you how to feel. It never asks for more material,
because "add tension" just produces longer dead prose.

**Lens, trigger, authority.** A reader used to weld three unrelated decisions into one class. They
are separate now: the **lens** is the questions and the stance — the checker class itself; the
**trigger** is the scope it fires on (every unit, scenes only, assembled chapters only) plus whether
it is sampled; the **authority** is what it may do about what it finds — `ESCALATE` (may block and
may reach the adjudicator), `BLOCK` (may block, but an escalation is capped into a blocking issue,
because a reader that has never seen immutable ground truth should not stop a run), or `ADVISE`
(findings are recorded as warnings and block nothing). One `ReaderSpec` row binds the three plus a
note saying why; the shipped gate is the `PROSE_GATE` table in
[`src/storica/checkers/registry.py`](src/storica/checkers/registry.py). A lens can now be pointed at
a new seam without being rewritten — Intent is one lens reading the arc, each chapter spec and each
assembled chapter, which closes the gap that no reader ever judged whether a chapter *delivered* its
assigned beats. It advises rather than blocks there because it has never been calibrated, and
vitality is the standing lesson about what an uncalibrated binary gate does to a book; promoting it
after calibration is a one-word change to its row. Scope is also a cost lever: an out-of-scope unit
costs no model call, so the assembled chapter is read by two readers, not five. [`docs/agents.md`](docs/agents.md) is the full roster — every agent, what triggers it, what it
reads, and what it may do.

### When something can't be repaired locally

`ESCALATE` fires when a unit contradicts canon, canon contradicts itself, or an assigned beat is
unsatisfiable. The run does not pause. Instead:

1. A fresh **adjudicator** gets the conflict, the checker's located issues, the **frozen ground
   truth** (the brief plus the canon locked at stage 2) and the decision log, and issues exactly one
   binding ruling: correct the unit, or — only if canon itself violates ground truth — amend canon.
2. The ruling is appended to `05_reports/decisions.jsonl` and is **binding**. The same conflict can
   never be reopened, and every ruling is carried into each later re-attempt of the chapter, which
   is what guarantees the run converges instead of oscillating. A ruling has consequences: at
   reconcile, `correct_the_unit` sends the saved draft through one grounded repair pass bound by the
   ruling's instruction; `amend_canon` quarantines the chapter and commits nothing to canon, because
   an excluded chapter must not leave facts behind.
3. If repair budget runs out anyway, the chapter is **quarantined** — logged, and excluded from
   `novel.md` rather than shipped broken. A chapter spec or reconcile that cannot pass its gate is
   quarantined the same way instead of crashing the run.

**Planning escalations are adjudicated too.** The macro arc and each chapter spec are now wrapped the
way prose has always been: an Intent escalation goes to the adjudicator, the ruling is logged and
binds the re-attempt, and guidance accumulates across rulings so a second escalation does not make
the stage forget the first. A ruling that would amend canon stops the stage instead — canon is never
rewritten to settle a planning conflict. When the escalation budget runs out, the stage fails its own
gate and the caller contains it: a chapter-spec escalation quarantines that chapter, a macro-arc one
stops the run with `[failed]` and exit 1. Both were uncaught tracebacks before.

Quarantine is not permanent. `storica run --retry-quarantined` releases every quarantined chapter
(the release is appended to `quarantine.jsonl`; the original record stays) and attempts it again,
typically with a larger `--max-repairs`. Only canon (stages 1–2) and the macro arc (stage 3) have no
chapter to quarantine into: if one of those fails its gate the CLI prints `[failed]` with the issues
and exits 1, as does a model refusal (`[refused]`).

This is the direct answer to v1's worst failure: an agent told to reconcile a contradiction invented
a bridging fact, and the invention became canon. Repair here can only resolve *toward* something
frozen, so it has nothing to invent with.

### What reconcile carries forward

After a chapter passes, reconcile extracts what the prose established and promotes it into canon, so
the next chapter is written against it. The extractor classifies each fact as new, a restatement or
a contradiction (only a reader can tell a paraphrase from a change — restatements are recorded, never
adjudicated); places each event in *story* order, so a past event the chapter reveals does not sort
after last night; and records **knowledge shifts** — a character who learns or starts to suspect
something on the page holds it from that chapter on. Knowledge only moves forward, and a shift the
plan scheduled for a later chapter arriving early is flagged. The slice every agent reads renders
knowledge *as of the chapter being written*.

---

## Where to find what

```
storica/
├── README.md              you are here
├── DESIGN.md              the v2 architecture spec and its reasoning — the document to read
├── .env.example           ANTHROPIC_API_KEY, needed only for --driver anthropic
│
├── pyproject.toml         deps and the `storica` console script
│
├── src/storica/           ← THE PIPELINE
│   ├── cli.py             new / run / status
│   ├── runner.py          the run loop; resumable by construction
│   ├── pipeline.py        I/O only: load from disk, run the stage, write back
│   ├── chapter.py         one chapter's attempt loop: escalate → adjudicate → retry → quarantine
│   ├── drafts.py          reading and writing 03_drafts/
│   ├── brief.py           the front-door brief — immutable ground truth
│   ├── authors.py         loads the author library
│   ├── canon/             story_model.json: model, validation, ids, slicing, versioned store
│   ├── plan/              macro arc + chapter specs: schema, validation, store
│   ├── stages/            conception, world_cast, macro_arc, chapter_spec, prose/, reconcile/
│   │   ├── gate.py            the shared generate → check → repair loop
│   │   ├── prose/             prompts · selection · quality (the hand-written loop)
│   │   └── reconcile/         schema · prompts · promote · ledger
│   ├── checkers/          base (the one shared call), prose_base (the shared prose gate) +
│   │                      canon_consistency, intent, micro_sense, voice, vitality, auditor,
│   │                      consensus, defaults, and registry.py — the gate as policy:
│   │                      lens × trigger × authority, in one readable table
│   ├── adjudicator.py     binding rulings against frozen ground truth
│   ├── reports.py         decision log, quarantine log, run report
│   ├── assembly.py        chapters → novel.md, excluding quarantined units
│   ├── trace.py           every filled prompt and artifact, to 04_trace/
│   ├── llm.py             the only place the Anthropic SDK is touched; model aliases
│   └── drivers/replay.py  run the real prompts with no API key
├── tests/                 327 tests
│
├── authors/               author library, shared across novels — see authors/README.md
│   ├── duerrenmatt/
│   └── hemingway/
│
├── novels/                one folder per novel — see novels/README.md
│   ├── _template/             empty skeleton to copy
│   ├── der-chrachen/          the v1 capture kept as reference evidence
│   └── der-chrachen-v2/       the P6 run: same story under v2, in progress
│
├── tools/                 calibrate_checkers.py — known-answer test for the checker layer
│                       smoke_test_api.py    — proves the live adapter works, for ~$0.001
│                       next_call.sh         — prints the next pending replay call (run from repo root)
├── calibration/           its results and FINDINGS.md
├── .claude/skills/write-novel/   the /write-novel skill: drive a run on a subscription
├── docs/agents.md         every agent: family, what fires it, what it reads, what it may do
├── docs/p6-handoff.md     the prompt for a fresh session to continue P6
├── docs/proving-the-concept.md   what the replay method does and does not prove
├── docs/archive/          point-in-time v1 documents, not maintained
└── legacy/                the archived v1 web app — see legacy/README.md
```

### A novel folder as it fills up

```
novels/<slug>/
  00_input/brief.yaml          ← you write this. Frozen after creation; nothing may edit it
  01_canon/
    story_model.json           the source of truth
    history/                   every accepted version — canon changes are auditable and reversible
  02_plan/
    macro_arc.json
    chapters/chNN.spec.json    written just in time, one chapter ahead of the prose
  03_drafts/chNN.md
  04_trace/                    every filled prompt and every artifact, per agent
  05_reports/                  each file appears when it is first needed
    decisions.jsonl            binding rulings — the record of every conflict and how it was settled
    quarantine.jsonl           units excluded from the book, and why; a release appends, never deletes
    state.json                 which chapters have been reconciled
  06_session/                  --driver replay only: the request/response cache
  novel.md                     the assembled book
```

Progress lives in the artifacts themselves, not a status file — which is why `run` is resumable and
why `status` can just look at the disk.

### Authors

An author is a folder of assets reused across novels: `profile.yaml` (philosophy, style, critique
rubric), `question_lines.md` (the obsessions this author has), `nudges.md`, `impression.md`, and
annotated `examples/` — which nothing in the pipeline reads yet. Dürrenmatt and Hemingway exist today.

The author is a **generative driver, not a paint job**: their question-lines feed Stage 1 and shape
*which story gets told*, not only how it sounds.

---

## Development

```bash
.venv/bin/python -m pytest -q      # 327 tests, a few seconds, no API key, no network
```

Model aliases (`opus`, `sonnet`, `haiku`) resolve to current model IDs in exactly one place —
`MODELS` in `src/storica/llm.py`. The SDK is pinned to `anthropic>=0.115,<1`; 1.x changes the HTTP
stack, so re-run `tools/smoke_test_api.py` before lifting it.

Two constraints the stage schemas must obey, both from Anthropic's structured-output support:
every model is `extra="forbid"`, and **no `Dict[...]` fields** — stages emit lists with explicit
ids, and the mapping into canon's dicts happens in Python. `src/storica/llm.py` documents this.

The source is written to be read: most modules open with a docstring explaining *why* they exist,
not just what they do. Start with `runner.py`, then `pipeline.py`.

---

## How we got here

Worth knowing, because it explains every design choice above.

v1 worked. Its prose was good sentence by sentence. To find out why the books still didn't hold
together, a complete run was captured by hand, prompt by prompt, using the exact v1 templates — that
capture is [`novels/der-chrachen/`](novels/der-chrachen/), and the twelve findings are in
[`FINDINGS.md`](novels/der-chrachen/FINDINGS.md). Read the prompts next to their outputs and the
failure is visible happening.

What it showed: plans were coherent and sentences were coherent, but the **seam between them** was
not. Because each stage passed prose forward for the next to re-interpret, and because the story
bible was seeded from prose rather than ground truth, one early slip became permanent. The writer
recast a priest as a creditor; the consistency guardian recorded that as canon; the next chapter's
reasoner hit the contradiction and *invented a bridging fact* to smooth it over; and the revision
loop, asked to "make it consistent" without ever being shown the original character sheet, renamed
the victim and changed the cause of death from a fall to poisoning — breaking the central plot while
scoring *better*, because the surface complaints were gone.

Three distinct failures, which is why there are three kinds of checker: **coherence** (facts
silently change), **meaning** (coherent but hollow — nothing advances), and **micro-truth** (locally
fluent but nonsensical). One "make it more top-down" lever cannot move all three.

`der-chrachen/01_canon/story_model.json` is that same story written as v2 canon — 7 characters, 3
motifs, 2 promises — and it validates cleanly against the current schema. It is a worked example of
what stage 2 is supposed to produce.

---

## What's next — P6

`DESIGN.md` §9 lays out the build plan P0–P6. P0–P5 are implemented and tested. **P6 is the open
one:** run *Der Chrachen* end-to-end under v2 and compare it against the v1 capture — same spark,
same world, same author, same three chapters, so the comparison is direct.

It is set up and ready to run:

- **[`novels/der-chrachen-v2/`](novels/der-chrachen-v2/)** — the brief, a faithful translation of the
  v1 inputs. `question_lines`, `nudges` and `forbidden` are deliberately left empty even though v2
  supports them, because v1 had no equivalent; otherwise an improvement could be credited to a
  better brief rather than to the pipeline.
- **[`/write-novel`](.claude/skills/write-novel/SKILL.md)** — a skill that drives the run on a Claude
  subscription instead of the API, answering each call with a freshly spawned subagent.
- **[`docs/proving-the-concept.md`](docs/proving-the-concept.md)** — what that method does and does
  not prove, the contamination trap that would silently invalidate it, and the scorecard for judging
  the result against the v1 findings.

Run it with `/write-novel novels/der-chrachen-v2`. A scene at defaults is about ten calls, but the
fan-outs (three candidates, three canon-consistency draws, three scene readers) are answered in
parallel, so it is about five stops; a repair round adds two calls.

### How far the run has got, and what it has already shown

Canon v2 is established and validated, the macro arc committed, chapter 1 specced (four scenes) and
past its Intent check. The **first attempt at chapter 1 was quarantined** on scene 3 — and reading
the trace showed that the gate, not the prose, was at fault (`calibration/FINDINGS.md` C7):

- **Selection works and is cheap.** Three drafts of scene 1 at 937 / 871 / 739 words; the selector
  declined the longest. One call, and the spread was real.
- **The repair loop did not converge, by construction.** Every repair was followed by a full fresh
  re-read of the scene, and every fresh read asked a different question — the date *"Am elften März"*
  was a warning in read 1 (so repair never saw it), unmentioned in read 2, blocking in read 3.
- **The reader was stricter than the writer's instructions.** The writer was told to invent texture;
  micro-sense called any unglossed specific a hallucination.

The rework of 2026-09-21 fixed both (pinned issues verified per repair; one invention policy shared
by writer and reader), gave the writer the author's full craft and the whole chapter so far, closed
the three reconcile gaps (paraphrase, story order, knowledge that moves), and calibrated micro-sense
and voice (C8). Chapter 1 was released and is re-attempted from the same spec under the new gate;
everything before it replays from cache.

### What the calibration found first

Before P6, the checkers were pointed at the v1 chapters with correct canon in hand — a known-answer
test costing about ten calls instead of a whole book. Full write-up in
[`calibration/FINDINGS.md`](calibration/FINDINGS.md); reproduce with
`.venv/bin/python tools/calibrate_checkers.py`.

- **The checker works, and is not overfit.** It caught 4 of 5 planted errors, and scored *identically*
  with every mention of this book's failures stripped out of its rubric — so it detects contradiction
  rather than recognising der Chrachen. Zero false positives on the clean control chapter.
- **The reference canon was the broken part.** `novels/der-chrachen/01_canon/` had absorbed the exact
  F11 bridging fact ("priest *and* private creditor") that the findings condemn, because it was
  written by reading the corrupted v1 output. `DESIGN.md` §4's own example had it too. Both fixed;
  the design now says canon is authored from the brief and **never reconstructed from prose** — a
  rule that binds humans, not just agents.
- **The gate was not deterministic — now it is.** Drawing the same call five times: broken text
  blocked in 5/5, clean text in 1/5. So a single verdict is 20% noise on clean prose, and
  union-blocking ("repair if any draw complains") would reject good chapters **49%** of the time at
  k=3. The pipeline now takes a **majority of 3**, which drops that to ~10% while losing no recall —
  and once a majority blocks, repair sees the *union* of what every draw found. `--checker-samples 1`
  opts out.
- **The vitality checker would have flattened every chapter.** Tested on a matched pair — one chapter
  as written, the same one deliberately deadened — the *signal* separates threefold (2.5–5.1 vs
  15.7–18.1 blocking issues per 1000 words) and finds exactly the right sentences. But **both** got
  `revise` every time, because good prose also has two or three places a sharp reader would cut.
  Under "any issue → repair" it fires on everything, sending the whole book through the step that
  flattens prose — it would have caused the failure it exists to prevent. It now gates on **density**,
  not presence.
- **Two of the original findings were artefacts.** At n=1 an unlucky draw is indistinguishable from a
  real miss; resampling overturned both. Worth knowing before trusting any single verdict here.

- **P6's first chapter was killed by the gate, not the prose (C7).** Each repair was followed by a
  full fresh re-read, and each re-read asked a different question: a date was a warning in read 1,
  ignored in read 2, blocking in read 3. And micro-sense held the writer to a stricter rule about
  invented detail than the writer had been given. Fixed by pinning issues and verifying repairs
  against them, and by one invention policy shared by writer and reader.
- **Micro-sense and voice now pass their floor test (C8).** Neither blocked the clean control chapter
  in any of three draws; both blocked the broken version every time; micro-sense caught the planted
  breaches (a named stranger, an impossible hand-over, an abstraction, a self-contradiction) and
  blocked none of the twelve permitted specifics, dates included. Reproduce with
  `.venv/bin/python tools/calibrate_readers.py`.

Known open questions, in `DESIGN.md` §10: every planted error tested was a *fact* changing, not a
contradiction of tone or motive; every calibration is n=3–5 on one chapter of one author; the repair
verifier and intent-on-prose are unmeasured; cost per book versus v1 is unmeasured.

---

*Where the unwritten waits.*
