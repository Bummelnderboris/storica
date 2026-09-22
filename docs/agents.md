# The agents

Every model call in a Storica run belongs to one of four families. This is the roster: which agents
exist, what wakes each one, what it may read, and what it may do about what it finds. The reasoning
behind the stages is [`DESIGN.md`](../DESIGN.md) §5, and behind the verification layer §6.

## The four families

- **Makers** produce a unit — a premise, canon, a plan, prose. They are the only agents that write.
  The prose agent is also the repair agent: same system prompt, same model, handed the flagged spans
  instead of a blank page.
- **The extractor** (reconcile) reads a finished chapter and proposes facts. It never writes canon
  directly; every extracted item is promoted, ignored as already-known, or flagged as a contradiction.
- **The judges** read a unit they did not produce and return a verdict. They never rewrite.
- **The arbiter** (adjudicator) settles what a judge could not resolve locally, once and bindingly.

## The roster

Model tiers are `STAGE_MODELS` in [`src/storica/llm.py`](../src/storica/llm.py): opus for invention
and for the calls that must not be wrong, sonnet for structured transformation and judgement against
a slice.

| Agent | Family | Fires when | Reads | Authority | Model |
|---|---|---|---|---|---|
| **Conception** | maker | stage 1, once | brief × author model | writes `canon.premise` | opus |
| **World & cast** | maker | stage 2, once | premise, brief, author | writes characters, relationships, world facts, timeline, knowledge, constraints | sonnet |
| **Macro arc** | maker | stage 3, once | full canon | writes `02_plan/macro_arc.json` | sonnet |
| **Chapter spec** | maker | stage 4, just in time, one chapter ahead of the prose | canon *as it now stands*, the arc, the previous spec | writes `chNN.spec.json` | sonnet |
| **Prose** | maker | stage 5, once per scene — *k* times with `--prose-candidates k` | the scene's assignment, `canon_slice` for exactly what it touches (knowledge as of this chapter), the author's craft (`writer_block`), the invention policy, and the chapter so far | writes the scene | opus |
| **Repair** | maker (the prose agent) | any pinned blocking issue, and any `correct_the_unit` ruling against a saved draft | the current text, the pinned issues, the same canon slice | rewrites only the named spans; may invent nothing | opus |
| **Repair verifier** | judge | after each prose repair round | the pinned issues + a paragraph diff of what the repair changed + the canon slice — never the unchanged text | resolved/unresolved per pin, plus damage the edit did; cannot raise anything else | sonnet |
| **Reconcile** | extractor | stage 6, after a chapter passes its gate | the draft, the spec, the canon slice | proposes facts (classified new / restatement / contradiction), timeline events in story order, knowledge shifts, and ledger outcomes; promote / ignore / **flag** | sonnet |
| **canon_consistency** | judge | every scene and the assembled chapter; sampled *k* times (`--checker-samples`) | the unit + its canon slice | escalate | sonnet |
| **micro_sense** | judge | every **scene** | the unit + its canon slice + the invention policy the writer was given | escalate | sonnet |
| **voice** | judge | every **scene** | the unit + the same author craft block the writer had + the brief's forbidden list | escalate | sonnet |
| **vitality** | judge | every **scene** | the unit + a deliberately **thin** slice (premise, constraints) | escalate; blocks on issue *density*, not presence | sonnet |
| **intent** | judge | the macro arc (3), each chapter spec (4), each **assembled chapter** (5) — never a scene | the unit + the assignment it was given + canon slice | escalate on plans; **advise** on prose | sonnet |
| **Selector** | judge | per scene, when `--prose-candidates > 1` | the *k* drafts and nothing else — no canon, no rubric of correctness | picks one; returns no verdict and cannot block | sonnet |
| **Final auditor** | judge | once, after assembly (`--no-audit` skips it) | the whole novel, canon, the arc, and `audit_ledger`'s findings | pass / revise / escalate on the book | opus |
| **Audit repair** | maker (the prose agent) | the final audit returns `revise` with blocking findings (`--audit-repairs` rounds) | one chapter's text, the findings routed to it, the chapter's canon slice | edits only what the findings name; a rewrite is rejected; verified by the repair verifier; then a fresh audit | opus |
| **Adjudicator** | arbiter | any escalation that reaches it, from prose or from a planning stage | the conflict, the **immutable ground truth** (brief + stage-2 canon), the decision log | exactly one binding ruling, appended to `decisions.jsonl` | opus |

## Before any model call: the deterministic gates

Four checks cost nothing and therefore run first. Each one catches a mechanical failure that no
amount of judgement should be spent on:

| Check | Where | Gates |
|---|---|---|
| `validate` | `canon/validation.py` | every canon write: dangling ids, name fragmentation, ledger and timeline sanity |
| `validate_macro_arc_draft` · `validate_chapter_spec` · `validate_continuity` | `plan/validation.py` | stages 3 and 4, **before** Intent is called — so Intent judges meaning, not bookkeeping |
| `audit_ledger` | `checkers/auditor.py` | the final audit: the promise/motif ledger is walked mechanically and the result goes *into* the auditor's prompt |
| `_deterministic_issues` | `stages/prose/quality.py` | every prose unit: empty, or shorter than `MIN_SCENE_CHARS` (400) — runs before the selector, so no judgement is spent comparing stubs |

## How they relate

The graph is one-directional and deliberately amnesiac.

- A maker produces. Fresh judges then read the result **with no memory of how it was made** — no
  drafts, no prompts, no knowledge of which units were hard. The writer is blind to its own drift, so
  it never judges its own work.
- Only the judges' **issue list** flows back, into a repair. Nothing else crosses: no judge sees
  another judge's verdict, and no two agents converse.
- **A unit is judged in full once.** Its blocking issues are pinned; after each repair the repair
  verifier checks the pins against a diff, and nothing else. Re-running the full gate re-rolled the
  question every round and never converged (`calibration/FINDINGS.md` C7). Only a repair that
  rewrote the unit instead of editing it is read in full again.
- **The judges and the maker share their rules.** The writer and micro-sense read one invention
  policy (`canon/invention.py`); the writer and voice read one author block. A judge that holds the
  maker to a rule the maker was never shown is a gate that fails good work.
- **canon_consistency runs first and short-circuits.** When it blocks, micro_sense, voice, vitality
  and intent are not spent on that draft — they read the repaired text instead. A contradiction makes
  every other judgement moot. When it passes, the remaining readers run **concurrently**; under the
  replay driver that means one stop asks all of them at once.
- A judge that thinks *canon* is wrong does not tell the maker. It escalates to the arbiter, which is
  the only agent holding immutable ground truth. This is the F11 rule in structural form: nothing
  downstream may resolve a contradiction by inventing a bridging fact.
- Rulings are binding and logged, and every earlier ruling rides into each later re-attempt of the
  unit. That is the convergence guarantee — the same conflict cannot be re-opened or oscillate.

## Re-pointing a reader

A reader is three independent decisions, and only the first is worth writing carefully:

- **lens** — the questions and the stance. That is the checker class.
- **trigger** — `Scope.UNIT` / `Scope.SCENE` / `Scope.CHAPTER`, plus whether it is sampled *k* times.
- **authority** — `Authority.ESCALATE` (may block and may reach the arbiter), `Authority.BLOCK` (may
  block; an escalation is capped into a blocking issue, because a reader that has never been shown
  ground truth should not be able to stop a run), `Authority.ADVISE` (findings are demoted to
  warnings and recorded; never blocks, never escalates).

All three live in one row of `PROSE_GATE` in
[`src/storica/checkers/registry.py`](../src/storica/checkers/registry.py). To add or re-point a
reader, write the row:

```python
ReaderSpec(
    lens=lambda llm, tracer: MicroSenseChecker(llm, tracer=tracer),
    scope=Scope.SCENE,          # scenes only — the assembled chapter costs no call at all
    authority=Authority.BLOCK,  # may force a repair, may not reach the adjudicator
    sampled=True,               # k draws, majority blocks, union reports (--checker-samples)
    note="why this row is configured this way — read by humans, not by code",
)
```

Each knob is enforced by a wrapper that preserves the lens's `name`, so the gate's short-circuit
still recognises it: `ScopedProseChecker` returns a pass without a model call when the unit is out of
scope, `ConsensusProseChecker` draws *k* times, and `BoundedProseChecker` caps what the verdict may
do — it never discards a finding, only its teeth.

Promoting intent from advisory to blocking, once it has been calibrated, is a one-word change to its
row: `Authority.ADVISE` → `Authority.BLOCK`.

## What is deliberately absent

- **No thinker.** Nothing in this pipeline reflects between chapters — no agent reads what the book
  has become and reconsiders. Conception is the closest thing, and it **grades its own candidates**:
  it generates a few stories this author would tell and then chooses among them itself. That is the
  one place a maker judges its own work, and it is tolerable only because it happens before any canon
  exists to be wrong about.
- **No separate specialist agent.** A `spawn_specialist` ruling emits a real sub-task, and
  `reports.binding_guidance()` now carries it (with the ruling's instruction) into the unit's own
  re-attempt — in the chapter loop and in the planning loop alike. It used to be dropped on the
  floor, so this is an improvement, but it is still weaker than handing the sub-task to a dedicated
  fresh agent. DESIGN §10 carries it as a known limitation.
- **Intent has no teeth on prose.** It reads every assembled chapter and records what it finds, and
  nothing it finds can block. It has never been calibrated, and vitality is the standing lesson:
  an uncalibrated binary gate fires on everything and sends the whole book through the step that
  flattens prose (`calibration/FINDINGS.md` C6).
