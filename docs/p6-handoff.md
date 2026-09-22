# P6 handoff — the prompt for a fresh session

Paste the block below into a **new** Claude Code session in this repo.

## The run is finished

P6 completed on 2026-09-22: three chapters, ~14k words in `novel.md`, nothing quarantined, no
chapter-level rulings, and a final audit of `pass` after three audit-repair rounds. `storica run`
on this novel now replays the whole thing and exits 0; there is nothing left to answer.

What remains is not a run but a reading: compare the book against the v1 capture with the scorecard
in [`proving-the-concept.md`](proving-the-concept.md), and read `05_reports/` before `novel.md`.

This document is kept for the next novel, and for what it says about pace and hygiene below.

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

Then loop: run the CLI, read every call listed under [pending], dispatch one fresh subagent per
call — in parallel — and repeat once they have all finished.
  .venv/bin/storica run novels/der-chrachen-v2 --driver replay

Exit codes: 0 = done, 1 = canon or the macro arc failed its gate ([failed], with the issues) or the
model refused a call ([refused]) — report it, do not patch around it; 2 = a call needs an answer;
3 = a recorded answer was malformed (delete that response file and re-dispatch); anything else = a
real bug, stop and report the traceback. A chapter that fails is quarantined, not a stop: if
05_reports/quarantine.jsonl grows, say so in the next report and keep going. Do not pass
--retry-quarantined unless I tell you to.

Dispatch each subagent on the model its [pending] line names (model=claude-opus-5 -> opus,
model=claude-sonnet-5 -> sonnet). You never need to open a request file. Report every ~10 calls in one line: stage names
answered, count so far, anything quarantined. Do not summarise the story and do not quote the prose.

Cost note: prose defaults to 3 candidate drafts per scene plus a selection call. If you want a
cheaper pass, add --prose-candidates 1 --checker-samples 1 to every run command, but say so in
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
   [C6/C7](../calibration/FINDINGS.md) recurring. Chapter 1's first attempt was exactly this, and
   the rework addressed its two causes; micro-sense and voice have now had a floor test (C8), but on
   one chapter of one author. If the repair count per chapter is high and the repairs are not
   obviously improving anything, suspect the gate before suspecting the prose — and read the
   `repair_verify_*` records in `04_trace/`: they say, per pinned issue, whether the repair
   resolved it.

A run that reveals either of those is a successful run. The book is the deliverable; the reports are
the measurement.
