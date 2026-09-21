# P6 handoff — the prompt for a fresh session

Paste the block below into a **new** Claude Code session in this repo.

## The run is already part-done — it resumes, it does not restart

**Canon v2 is established and validated** (4 characters, 5 relationships, 7 timeline events,
3 knowledge items), the **macro arc is committed** (3 acts, 3 turning points, 8 beats, 2 motifs,
4 promises) and **chapter 1 is specced** (four scenes, passed its Intent check). All of that is on
disk and is not asked again.

Chapter 1's first attempt was **quarantined on 2026-08-11**, and the trace showed the cause was the
gate rather than the prose (`calibration/FINDINGS.md` C7): the repair loop re-read the scene in full
after every repair and got a different question each time, and micro-sense held the writer to a
stricter invention rule than the writer had been given. The rework of 2026-09-21 fixed both
(DESIGN §5.2, §6.2) and released the chapter. Because the writer's and the readers' prompts changed,
the cached answers for chapter 1's prose no longer match any request: chapter 1 is written afresh,
from the same spec, under the new gate. Everything cached before it still replays.

Every answered call is cached in `06_session/`, so `storica run` replays the lot and stops at the
first unanswered call. Do not delete that directory. Request files that are not listed under
`[pending]` in the run's output are left over from earlier runs and will not be asked again.

## Pace

One subagent round-trip took 1–25 minutes in the first attempt. What has changed since:

- **Fan-outs are answered in parallel.** The run prints every call it is waiting on (`[pending]`);
  the three prose candidates, the three canon-consistency draws and the three scene readers each
  arrive together. A scene at defaults is ~10 calls but ~5 stops.
- **A repair round is two calls** (repair + verification), not five to seven, and it converges.

Defaults (`--prose-candidates 3 --checker-samples 3 --max-repairs 3`) are the recommended config
now. `--prose-candidates 1 --checker-samples 1` remains the cheap option; if you use it, use it on
**every** run, or cached scenes will flip between the two behaviours.

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
