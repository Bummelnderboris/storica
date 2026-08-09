# P6 handoff — the prompt for a fresh session

Paste the block below into a **new** Claude Code session in this repo.

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

Exit codes: 0 = done, 2 = a call needs an answer, 3 = a recorded answer was malformed (delete that
response file and re-dispatch), anything else = a real bug, stop and report the traceback.

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
the part no automated test can tell you — and it is more informative than the prose, because a run
where nothing ever blocked means the gate is not working, however good the book turns out.
