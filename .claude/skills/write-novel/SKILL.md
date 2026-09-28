---
name: write-novel
description: Drive an autonomous Storica run (`storica run`, the P6-style benchmark pipeline) to completion on a Claude subscription by answering the replay driver's requests with fresh subagents. Use only when asked to run, continue or resume an autonomous run such as novels/der-chrachen-v2. For writing or developing a book with the user, use the develop skill instead.
---

# Drive a Storica novel with the replay driver

You are the **orchestrator**. You do not write any part of the novel. You run a command, see which
model call it is waiting on, and dispatch a fresh subagent to answer that one call. Then you repeat.

Usage: `/write-novel novels/<slug>` (defaults to `novels/der-chrachen-v2` if no path given).

## The one rule that makes this valid

**Every response is written by a newly spawned subagent that has read nothing else.**

Storica's central design claim is that verification works because each checker is a *fresh context*
reading a unit against canon with no memory of having written it (DESIGN §6, principle 4). If you
answer a prose call and then answer that chapter's micro-sense check yourself, the checker is the
author grading its own homework — it will rationalise instead of catching. The run would sail
through, the book would look validated, and the result would be worthless: you would have proven
only that Claude agrees with itself.

So:

- **Never** write a response file yourself. Not once, not "just this small one".
- **Never** read a request file's prompt, or any canon/plan/draft file, into your own context. Your
  opinions about the story must not exist. The only thing you may read from a request file is its
  `- model:` line (see dispatch below).
  The same holds for `05_reports/agent_map.html` and `storica map`: the map embeds every prompt of
  the run. It is for the human, after the run.
- **One subagent answers exactly one call**, then is discarded. Never reuse a subagent for a second
  call, and never batch several calls into one subagent.

If you catch yourself forming a view about the plot, you have already contaminated the run. Stop and
say so rather than continuing.

## Setup

```bash
.venv/bin/storica status <novel_dir>     # where things stand
```

If the novel does not exist yet, create it and stop so the human can write the brief:

```bash
.venv/bin/storica new <novel_dir> --author <author_id> --language <lang> --chapters <n>
```

## The loop

Repeat until done:

**1. Advance the pipeline.**

```bash
.venv/bin/storica run <novel_dir> --driver replay
```

**2. Branch on the exit code.**

| Exit | Meaning | Do |
|---|---|---|
| `0` | The run finished | Go to *Finishing* |
| `1` | Canon or the macro arc failed its gate (`[failed]`, with the issues), or the model refused a call (`[refused]`) | Stop. Report the printed issues verbatim. Do not retry or patch around it |
| `2` | A call needs an answer | Continue to step 3 |
| `3` | A recorded answer does not fit its schema | Delete the named response file, then re-dispatch that call with the validation error appended to the subagent's prompt |
| other | A real bug | Stop. Report the traceback verbatim. Do not try to patch around it |

**3. Read the pending calls from the output.** Exit 2 prints the first call, then every call this
run is waiting on:

```
[paused] awaiting response for '<stage>' [<key>]
  read:  <REQUEST_PATH>
  write: <RESPONSE_PATH>
...
[pending] 3 call(s) awaiting an answer in this run:
  - model=claude-opus-5 read=<REQUEST_PATH> write=<RESPONSE_PATH>
  - model=claude-opus-5 read=<REQUEST_PATH> write=<RESPONSE_PATH>
  - model=claude-opus-5 read=<REQUEST_PATH> write=<RESPONSE_PATH>
```

Several calls are pending at once wherever the pipeline fans out: *k* prose candidates, *k*
consensus draws of canon-consistency, and the three independent scene readers (micro-sense, voice,
vitality). Answer **every** `[pending]` line before re-running, and dispatch them **in parallel** —
one fresh subagent per line, all in one message. They are independent calls; answering them one
stop at a time only multiplies the wall-clock. Ignore request files that are not in the `[pending]`
list: they belong to earlier runs and may never be asked again.

**4. Pick the model.** Each `[pending]` line names it (`model=`); for the single `[paused]` call,
this is the only inspection of the request file you may do:

```bash
grep '^- model:' <REQUEST_PATH>
```

`claude-opus-5` → dispatch with `model: "opus"`. `claude-sonnet-5` → `model: "sonnet"`. Matching
the model keeps the run faithful to what the API path would do.

**5. Dispatch one fresh subagent per pending call** (`subagent_type: "general-purpose"`, `model` as
above), all in parallel, each with exactly this prompt and nothing added:

> You are a single stateless model call inside an automated pipeline. You are not an assistant and
> there is no conversation.
>
> Read this one file: `<REQUEST_PATH>`
>
> It contains a system prompt, a user prompt, and — if the call expects structured output — a JSON
> schema. Obey it exactly as if it were the entire context of an API request, because it is.
>
> **Read no other file. Do not list directories, search the repo, or look at the novel's canon,
> plan or drafts.** The request already contains every fact you are permitted to use. Anything you
> gather elsewhere is contamination and invalidates the run.
>
> Write your answer to: `<RESPONSE_PATH>`
>
> - If the request specifies a JSON schema: write **only** a single JSON object matching it. No
>   markdown fences, no commentary, no trailing prose. Every required field must be present, and
>   fields the schema forbids must be absent.
> - If the request asks for prose: write **only** the prose as markdown. No preamble, no fences, no
>   notes about your choices.
>
> Do not ask questions, do not explain yourself, and do not report back — writing the file is your
> entire output. Answer in the language the prompt is written in. When the file is written, your
> final reply is the single word `done` — no summary of what you wrote, because whoever reads your
> reply must not learn anything about the story.

**6. When every dispatched subagent has finished, go back to step 1.** The answered calls now replay
from cache and the pipeline moves on.

A chapter that exhausts its repair budget, or fails its spec or reconcile gate, is **quarantined**,
not a stop: the run continues with the next chapter and the reason lands in
`05_reports/quarantine.jsonl`. Mention it in your next report and keep going. A quarantined chapter
is skipped on every later run unless the human asks for `--retry-quarantined` (usually with a larger
`--max-repairs`); do not add that flag on your own.

## Pace and reporting

A scene costs roughly ten calls at defaults (three candidates, a selection, three canon-consistency
draws, three scene readers), plus two per repair round (the repair and one verification). The
chapter adds canon-consistency and intent on the assembly, then reconcile. Because the fan-outs
answer in parallel, a scene is about five *stops*, not ten. Work through them steadily without
checking in — the run is meant to be unattended.

Report only every ~10 calls, in one line: the stage names answered, the count so far, and anything
quarantined. Do not summarise the story. Do not quote the prose. You have not read it and must not.

If the same call needs re-answering more than **three** times, stop and report — that means a schema
the model cannot satisfy, which is a real finding about the pipeline and worth more than a
brute-forced answer.

## Finishing

On exit `0`:

```bash
.venv/bin/storica status <novel_dir>
```

Report, without editorialising about the story:

- chapters written, and anything quarantined (with the reason from `05_reports/quarantine.jsonl`)
- the final audit decision and summary
- how many binding rulings were issued (`wc -l 05_reports/decisions.jsonl`)
- where the book is (`<novel_dir>/novel.md`)

Then hand back to the human to read it. **You must not review the novel's quality yourself** — you
orchestrated its creation, so you are the one reader in the building whose opinion of it is worth
nothing.
