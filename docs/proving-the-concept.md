# Proving the concept on a subscription, not the API

**The question:** can we validate the v2 design by having a Claude Code session play the model —
answering each call by hand on a Pro/Max subscription — before spending anything on API calls?

**The answer: yes, for the thing that actually needs proving — provided one specific trap is
avoided.** This document says what the method does and does not establish, so the eventual switch
to `--driver anthropic` is a known quantity rather than a leap.

---

## How it works

`--driver replay` (`src/storica/drivers/replay.py`) is a `StructuredLLM` backed by files. For each
call it computes a content hash of `(model, system, prompt, schema)`. If `responses/<key>.*` exists
it replays it instantly; if not, it writes a self-contained request file and raises `ResponseNeeded`,
which stops the run. Someone writes the answer; the same command is run again; every already-answered
call replays from cache and the run continues from exactly where it stopped.

The pipeline cannot tell the difference. It is the same code path, the same prompts, the same gates.

The [`/write-novel`](../.claude/skills/write-novel/SKILL.md) skill automates the human side: it runs
the command, reads which call is pending, and dispatches a subagent to answer it.

---

## What this genuinely validates

**1. The design thesis itself — which is the whole point.** Does holding intent in a structured
canon, elaborating top-down just-in-time, and guarding every seam with fresh canon-armed checkers
actually produce a coherent, meaningful book? That question is about *architecture*, and the
architecture is exercised identically here. This is the thing P6 exists to answer, and replay
answers it.

**2. The prompts.** They are byte-identical to what the API would receive — the request file is
generated from the same strings. A prompt that is confusing, under-specified, or missing a variable
will be just as confusing here. This is the cheapest possible way to find that out.

**3. The orchestration.** Stage order, gate triggers, repair loops, escalation, adjudication against
frozen ground truth, quarantine, assembly, and resume are all real code running for real.

**4. Schema *design*.** Whether a schema is even answerable — whether it asks for things a model can
actually produce, whether it is internally contradictory, whether required fields make sense.

**5. Cost of being wrong: zero.** A prompt that turns out to be broken on call 40 costs nothing but
time. This is the strongest argument for doing it this way first.

---

## What it does NOT validate

These four must be re-established on the API. None of them are reasons to skip the replay run; they
are reasons not to declare victory after it.

**1. Constrained decoding.** The API path uses `messages.parse`, which constrains generation to the
schema at the token level. A subagent writing a JSON file is *unconstrained* — it can think, revise,
and reread before saving. Constrained decoding is a genuinely different generative regime and can
shift output quality, particularly on long or deeply nested schemas. So "an agent could satisfy this
schema" is weaker evidence than "the model can satisfy it under constraint."

**2. The call conditions.** A production call is a bare request with
`system="You are part of an autonomous novel-writing pipeline."` and nothing else. A Claude Code
subagent carries a large harness system prompt, tool definitions, and a working directory. Same
underlying model, meaningfully different conditions.

**3. Failure modes that only exist over HTTP.** Refusals (`stop_reason == "refusal"`), truncation at
`max_tokens`, timeouts, transient errors. `AnthropicStructuredLLM` handles all of these, and none of
that code runs under replay.

**4. Cost and latency.** Completely unmeasured. The per-book economics question stays open until a
real run.

---

## The trap: context contamination

This is the one thing that would silently invalidate the entire exercise, and it is worth stating
bluntly because the failure is *invisible*.

The design's load-bearing claim is that verification works because checkers are **fresh contexts**
(DESIGN principle 4: *"the writer is blind to its own drift"*). If a single session writes chapter
1's prose and then, a few calls later, also writes the micro-sense verdict on chapter 1, that
checker is not fresh. It remembers making those choices, and it will defend them. It will pass.

The result is a **false positive**: a book that cleared every gate, a run report full of passes, and
no evidence whatsoever — because what was actually tested was "does Claude agree with itself,"
which it reliably does.

Note this failure is worse than a plain bug, because it produces a *pleasing* result. A contaminated
run looks exactly like a successful one.

**The mitigation, enforced by the skill:**

- one freshly spawned subagent per call, discarded afterwards — never reused, never batched;
- the subagent is told to read *only* the request file and explicitly forbidden from exploring the
  repo, so it sees exactly the canon slice the pipeline chose to give it — no more, which is the
  fidelity point;
- the orchestrating session never writes a response and never reads a prompt or artifact, so it
  cannot start steering the story;
- the subagent is dispatched on the model the request names, so Sonnet stages are answered by Sonnet
  and Opus stages by Opus.

The request file being self-contained by design — system prompt, user prompt, and schema in one
file — is what makes this clean rather than aspirational.

---

## When to switch to the API

Replay has done its job when:

1. a book completes with nothing quarantined and a passing final audit;
2. reading it, you find the macro↔micro seam holds — no drifting facts, no hollow chapters, no
   locally-fluent nonsense (the three failure classes in DESIGN §2);
3. the prompts have stopped needing edits between runs.

A quarantine along the way does not contradict condition 1; it is the gate doing its job, and a run
that reveals blocking is a successful *run* — the [handoff](p6-handoff.md) says so and means it.
What it is not is a finished *book*. So after a quarantine, read `05_reports/quarantine.jsonl` and
the repair rounds in `04_trace/` first: if the issue is real and precisely located (P6's was — an
ungrounded date), release the chapter with `--retry-quarantined --max-repairs 4` and see whether the
loop converges given room; if the repairs were not improving anything, suspect the gate (C6 again)
before the prose, and fix the prompt. Either way the run continues; the book is only done when
condition 1 holds on the final assembly.

Condition 3 matters most. Every prompt fix found under replay is a fix you did not pay for. Switch
when you stop finding them — then run the same book on `--driver anthropic` and compare. Differences
at that point are attributable to constrained decoding and call conditions, which is a small, sharp
question rather than an open-ended one.

---

## P6: the comparison this is set up for

`novels/der-chrachen-v2/` re-runs the exact story of the v1 capture in `novels/der-chrachen/`: same
spark, same world, same conflict, same tone, same three chapters, same author.

Its brief deliberately leaves `question_lines`, `nudges` and `forbidden` **empty**, even though v2
supports them, because v1 had no equivalent input. Filling them would hand v2 steering v1 never had,
and any improvement could then be credited to a better brief rather than to the pipeline. Everything
v1 knew lives in `spark` and `thoughts`; nothing more.

What to compare afterwards, using the v1 findings as the scorecard:

| v1 failure | Where to look in the v2 run | Passing looks like |
|---|---|---|
| **F6/F9** a character silently changes role (the priest became a creditor) | `01_canon/history/` — every canon version | Roles stay fixed across versions; changes are deliberate and logged |
| **F10** the guardian wrote prose errors into canon as fact | `05_reports/decisions.jsonl` | Contradictions produced *rulings*, not silent absorption |
| **F11** an agent invented a bridging fact to smooth a contradiction | `decisions.jsonl` | Rulings resolve toward ground truth; no new facts appear from nowhere |
| **F12** the reviser "fixed" a chapter into incoherence | `03_drafts/` vs `04_trace/` repair rounds | Repairs narrow to flagged spans and do not rewrite settled facts |
| **F8** the 7.0 average gate could never fire | `05_reports/` verdicts | Checkers actually blocked something; issues are located, not averaged |
| **F7** name fragmentation inflating every prompt | `01_canon/story_model.json` | One ID per character, aliases collected, no duplicates |
| **F5** continuity threaded as `raw_blueprint[:800]` | `02_plan/chapters/*.spec.json` | Specs reference canon by ID, with real entry/exit state |

The honest bar: v2 has to beat v1 on *coherence, meaning and micro-truth*. It does not have to
produce better sentences — v1's sentences were already good, and that was never the problem.
