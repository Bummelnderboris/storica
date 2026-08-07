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
| **v2** | A canon-centric pipeline, run from the CLI | `src/storica/` | **Current.** 218 tests passing. Never yet run end-to-end against the real API |
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
(skip the whole-book final read), `--max-repairs N`.

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
| 5 | **Prose** | spec + **full canon slice** | *k* drafts per scene → select the most alive → `03_drafts/chNN.md` | Opus |
| 6 | **Reconcile** | draft + canon | extracts facts from the draft, validates them, promotes or flags; updates the ledger | Sonnet |

Stage 4 runs **just in time**, one chapter at a time, immediately before that chapter is written —
so it sees everything the previous chapters established. A frozen mega-outline written up front is
itself novel-length and drifts; this avoids that.

Stage 5 **selects rather than repairs**. It draws several independent drafts of each scene from the
identical prompt and one cheap call picks the most alive; only the winner enters the checker loop.
Repair is a regression-to-the-mean engine — every iteration moves a draft toward the rubric and away
from whatever was surprising in it — so the variance is better spent choosing than sanding. Cost is
*k* generate calls plus **one** judgement, not *k* gates. Use `--prose-candidates 1` to turn it off.

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
| **Canon-consistency** | Does this contradict a canonical fact, relationship or timeline entry? | every stage output |
| **Intent** | Does this advance the beats it was *assigned*? Does it keep its promises? | plans and prose |
| **Micro-sense** | Paragraph by paragraph: are details grounded, does the situation cohere, is the language load-bearing? | prose |
| **Author-voice** | Is this the author, and inside the forbidden list? | prose |
| **Vitality** | Is this *alive*? Does it explain its own gestures, announce its emotions, restate the outline? | prose |
| **Final auditor** | One fresh reader on the whole assembled book | once, at the end |

There is deliberately **no single averaged score**. v1 gated on a weighted mean of 7.0, which a
competent draft clears every time — so the gate could never fire on the thing that actually mattered.
Here any checker raising a blocking issue triggers repair, and checkers run on the smallest
meaningful unit so a problem is localised rather than averaged away. Cheap structural checks run
before expensive LLM ones.

**Vitality is the odd one out, on purpose.** The other four are conformance checks, so a chapter that
matches canon, hits its beats and sounds like the author passes the whole gate no matter how inert it
is — and since repair pushes prose toward the rubric, that is the chapter this pipeline naturally
produces. Vitality can only fail a unit for being *safe*, and its fixes are always cuts: the sentence
that explains the gesture, the adjective that tells you how to feel. It never asks for more material,
because "add tension" just produces longer dead prose.

### When something can't be repaired locally

`ESCALATE` fires when a unit contradicts canon, canon contradicts itself, or an assigned beat is
unsatisfiable. The run does not pause. Instead:

1. A fresh **adjudicator** gets the conflict, the **frozen ground truth** (the brief plus the canon
   locked at stage 2) and the decision log, and issues exactly one binding ruling: correct the unit,
   or — only if canon itself violates ground truth — amend canon.
2. The ruling is appended to `05_reports/decisions.jsonl` and is **binding**. The same conflict can
   never be reopened, which is what guarantees the run converges instead of oscillating.
3. If repair budget runs out anyway, the chapter is **quarantined** — logged, and excluded from
   `novel.md` rather than shipped broken.

This is the direct answer to v1's worst failure: an agent told to reconcile a contradiction invented
a bridging fact, and the invention became canon. Repair here can only resolve *toward* something
frozen, so it has nothing to invent with.

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
│   ├── pipeline.py        stage wiring: load from disk, run stage, write back
│   ├── brief.py           the front-door brief — immutable ground truth
│   ├── authors.py         loads the author library
│   ├── canon/             story_model.json: schema, validation, slicing, versioned store
│   ├── plan/              macro arc + chapter specs: schema, validation, store
│   ├── stages/            conception, world_cast, macro_arc, chapter_spec, prose, reconcile
│   ├── checkers/          canon_consistency, intent, micro_sense, voice, vitality, auditor
│   ├── adjudicator.py     binding rulings against frozen ground truth
│   ├── reports.py         decision log, quarantine log, run report
│   ├── assembly.py        chapters → novel.md, excluding quarantined units
│   ├── trace.py           every filled prompt and artifact, to 04_trace/
│   ├── llm.py             the only place the Anthropic SDK is touched; model aliases
│   └── drivers/replay.py  run the real prompts with no API key
├── tests/                 218 tests
│
├── authors/               author library, shared across novels — see authors/README.md
│   ├── duerrenmatt/
│   └── hemingway/
│
├── novels/                one folder per novel — see novels/README.md
│   ├── _template/             empty skeleton to copy
│   └── der-chrachen/          the v1 capture kept as reference evidence
│
├── tools/                 calibrate_checkers.py — known-answer test for the checker layer
├── calibration/           its results and FINDINGS.md
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
  05_reports/
    decisions.jsonl            binding rulings — the record of every conflict and how it was settled
    quarantine.jsonl           units excluded from the book, and why
    state.json                 which chapters have been reconciled
  06_session/                  --driver replay only: the request/response cache
  novel.md                     the assembled book
```

Progress lives in the artifacts themselves, not a status file — which is why `run` is resumable and
why `status` can just look at the disk.

### Authors

An author is a folder of assets reused across novels: `profile.yaml` (philosophy, style, critique
rubric), `question_lines.md` (the obsessions this author has), `nudges.md`, `impression.md`, and
annotated `examples/`. Dürrenmatt and Hemingway exist today.

The author is a **generative driver, not a paint job**: their question-lines feed Stage 1 and shape
*which story gets told*, not only how it sounds.

---

## Development

```bash
.venv/bin/python -m pytest -q      # 218 tests, ~1s, no API key, no network
```

Model aliases (`opus`, `sonnet`, `haiku`) resolve to current model IDs in exactly one place —
`MODELS` in `src/storica/llm.py`.

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

Run it with `/write-novel novels/der-chrachen-v2`. Expect roughly 40–60 model calls for three
chapters at `--prose-candidates 1`, more with selection on.

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
- **The gate is not deterministic.** The same call answered twice returned `revise` with a blocking
  issue and then `pass`. Unresolved, and it needs deciding before P6 or P6's result is unreadable.

Known open questions, in `DESIGN.md` §10: the sampling policy above; convergence caps need empirical
tuning; cost per book versus v1 is unmeasured.

---

*Where the unwritten waits.*
