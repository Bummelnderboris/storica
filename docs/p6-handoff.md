# P6 handoff — the prompt for a fresh session

Paste the block below into a **new** Claude Code session in this repo.

## The run is already part-done — it resumes, it does not restart

State as of the handoff (52 requests, 51 responses in `06_session/`): **canon v2 established and
validated** (4 characters, 5 relationships, 7 timeline events, 3 knowledge items, 0 issues),
**macro arc committed** (3 acts, 3 turning points, 8 beats, 2 motifs, 4 promises), **chapter 1
specced — four scenes — and passed its Intent check**, scenes 1–3 drafted with selection on (three
candidates each; scene 1 needed two repairs and passed), and **chapter 1 quarantined** on
2026-08-11: scene 3 spent its two repairs on one micro-sense issue, an ungrounded date (*"Am elften
März"*) the timeline does not fix, and scene 4 was never drafted. `05_reports/quarantine.jsonl`
holds the record; `03_drafts/`, `decisions.jsonl` and `state.json` do not exist yet — drafted prose
lives only in `04_trace/*.json` until a chapter passes. The next pending call is the **chapter 2
spec** (`06_session/requests/03605b6b645af714.request.md`, sonnet).

Every answered call is cached in `06_session/`, so `storica run` replays the lot in seconds and stops
at the first unanswered call. Do not delete that directory. The cached verdicts were produced before
commit `affe38b` fixed the consensus draw; request hashes were kept stable, so the run resumes at
the same call.

## After a quarantine: two ways forward

A quarantined chapter is skipped on every later run unless it is released. Either:

1. **Continue as-is.** Answer the chapter 2 spec and carry on; chapter 1 stays out of `novel.md`,
   and the run still measures everything downstream.
2. **Re-try chapter 1** with `--retry-quarantined --max-repairs 4`. The release is appended to
   `quarantine.jsonl` (the original record stays) and the chapter is attempted again. Under replay
   the cached candidates, selection and repair 1 replay from cache; repair 2 onward (each repair
   pass now has its own cache slot) and its
   checks need new answers. Use the flag on that run only — once released, the chapter is a normal
   chapter again.

## Pace: pick a config before you start

Measured on this run, one subagent round-trip takes **1–25 minutes** (the tail is long and
unpredictable). Per scene the shipped defaults cost ~10 calls; chapter 1 alone has four scenes, so
expect ~12 scenes, plus chapter-level checks, specs, reconciles and the audit. That is roughly
120–150 calls at defaults — many hours; 51 calls bought one quarantined chapter.

| config | calls/scene | what it still tests | what it gives up |
|---|---|---|---|
| defaults | ~10 | everything | finishing this decade |
| `--checker-samples 1` | ~8 | selection, all four checkers | majority sampling (C4) |
| `--checker-samples 1 --prose-candidates 1` | ~5 | all four checkers, the whole spine | selection (C6/§5.1) |
| `--retry-quarantined --max-repairs 4` | + ~2 per extra repair | whether the repair loop converges given room | nothing; add to any row |

**Recommended for a first complete book: `--checker-samples 1 --prose-candidates 1`**, then re-run at
defaults once it has finished once. Both dropped mechanisms are unit-tested and were watched working
live on this run (three drafts at 937/871/739 words, selector correctly declining the longest).

One caveat if you drop `--prose-candidates` to 1: scenes 1–3 have three drafts each already cached,
and a single-candidate run replays **draft A**, not the draft the selector chose. Their text will
change. Nothing is corrupted; the selection is simply discarded. Use the same flags on **every**
subsequent run or scenes will keep flipping between the two behaviours.

## Why a fresh session

Not context budget — contamination. The session that built this pipeline has read the v1 novel's
plot, `FINDINGS.md` and `DIVERGENCE.md` in detail: it knows Rutz is the priest, that Klara Vogel is
the victim, and how the v1 book fails. The orchestrator never writes prose, so that is not fatal, but
a clean session is better hygiene and the subagents stay fresh either way.

---

```
Run P6 for Storica: drive novels/der-chrachen-v2 to a finished novel using the /write-novel skill.

Read .claude/skills/write-novel/SKILL.md first and follow it exactly. The rule that matters most:
you are the orchestrator and you never write a response yourself. Every model call is answered by a
freshly spawned subagent that reads ONLY its request file. If you write even one answer, or read a
request's prompt into your own context, the run is invalid — the whole design claim is that checkers
are fresh contexts, and a checker that remembers writing the prose will defend it.

Start with:
  .venv/bin/storica status novels/der-chrachen-v2

Then loop: run the CLI, read which call is pending, dispatch one fresh subagent per call, repeat.
  .venv/bin/storica run novels/der-chrachen-v2 --driver replay

Exit codes: 0 = done, 1 = canon or the macro arc failed its gate ([failed], with the issues) or the
model refused a call ([refused]) — report it, do not patch around it; 2 = a call needs an answer;
3 = a recorded answer was malformed (delete that response file and re-dispatch); anything else = a
real bug, stop and report the traceback. A chapter that fails is quarantined, not a stop: if
05_reports/quarantine.jsonl grows, say so in the next report and keep going. Do not pass
--retry-quarantined unless I tell you to.

Dispatch each subagent on the model the request names (grep '^- model:' on the request file — that
is the only part of a request file you may look at). Report every ~10 calls in one line: stage names
answered, count so far, anything quarantined. Do not summarise the story and do not quote the prose.

Cost note: prose defaults to 3 candidate drafts per scene plus a selection call. If you want a
cheaper first pass, add --prose-candidates 1 --checker-samples 1 to every run command, but say so in
your final report, because both change what the run tests.

When it finishes, report: chapters written, anything quarantined and why (05_reports/quarantine.jsonl),
the final audit decision, how many binding rulings were issued (wc -l 05_reports/decisions.jsonl),
and where novel.md is. Do NOT review the novel's quality yourself — you orchestrated it, so your
opinion of it is the one opinion in the building that is worth nothing. Hand it to me to read.

Context you need, in order: /README.md, /DESIGN.md, /calibration/FINDINGS.md.
```

---

## What to do with the result

The book is the deliverable, but the run also answers questions the calibration could not. When it
is done, compare against the v1 capture using the scorecard in
[`proving-the-concept.md`](proving-the-concept.md) — same story, same author, same spark, so the
comparison is direct.

The honest bar: v2 has to beat v1 on **coherence, meaning and micro-truth**, not on sentences. v1's
sentences were already good; that was never the problem.

**Read `05_reports/` before you read `novel.md`.** Whether the checkers fired at all, and on what, is
the part no automated test can tell you — and it is more informative than the prose.

Two failure signatures to look for, in this order:

1. **Nothing ever blocked.** The gate is not working, however good the book turns out.
2. **Almost everything blocked, especially on micro-sense or voice.** This is
   [C6](../calibration/FINDINGS.md) recurring. Vitality had exactly this defect — every individual
   verdict defensible, the gate firing on every chapter regardless — and it was only caught by
   testing the *gate* rather than the judgements. Micro-sense and voice are still binary-gated and
   have never been calibrated, so they are the two most likely to carry the same flaw. If the repair
   count per chapter is high and the repairs are not obviously improving anything, suspect this
   before suspecting the prose.

A run that reveals either of those is a successful run. The book is the deliverable; the reports are
the measurement.
