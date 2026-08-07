---
name: write-novel
description: Drive a Storica novel to completion on a Claude subscription instead of the API, by answering the replay driver's requests with fresh subagents. Use when asked to run, continue, or resume a novel in novels/<slug>/, or to do a P6-style validation run.
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
| `2` | A call needs an answer | Continue to step 3 |
| `3` | A recorded answer does not fit its schema | Delete the named response file, then re-dispatch that call with the validation error appended to the subagent's prompt |
| other | A real bug | Stop. Report the traceback verbatim. Do not try to patch around it |

**3. Read the two paths from the output.** Exit 2 prints:

```
[paused] awaiting response for '<stage>' [<key>]
  read:  <REQUEST_PATH>
  write: <RESPONSE_PATH>
```

**4. Pick the model.** This is the only inspection of the request file you may do:

```bash
grep '^- model:' <REQUEST_PATH>
```

`claude-opus-5` → dispatch with `model: "opus"`. `claude-sonnet-5` → `model: "sonnet"`. Matching
the model keeps the run faithful to what the API path would do.

**5. Dispatch one fresh subagent** (`subagent_type: "general-purpose"`, `model` as above) with
exactly this prompt and nothing added:

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
> entire output. Answer in the language the prompt is written in.

**6. Go back to step 1.** The answered call now replays from cache and the pipeline moves on.

## Pace and reporting

A 3-chapter novel is roughly 40–60 calls; longer books scale from there. Work through them steadily
without checking in — the run is meant to be unattended.

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
