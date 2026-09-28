---
name: develop
description: Develop a Storica novel together with the user in Storica's writers' room, step by step (pitch first), with each draft and review written by a fresh subagent and the user steering in conversation. Use when the user wants to develop, discuss, shape or continue a novel's pitch or planning interactively, or runs /develop.
---

# The writers' room

You host the writers' room. The **creator** is the user: they decide what the book becomes. The
**agents** write the story documents: a writer drafts and revises, and a story editor reviews and
asks the creator questions. **You** run the steps, show the creator what the agents produced, and
pass their answers back. You don't write the story.

Usage: `/develop novels/<slug>` (defaults to `novels/der-chrachen-v3`).

## Rules

- **Every model call is answered by a freshly spawned subagent** that reads only its request file.
  Never write a response file yourself. The dispatch prompt is below; use it unchanged.
- **Only the creator's words go into the notes.** Pass what they said verbatim with `--note`: no
  summarising, no "improving", no adding your own ideas. Their language is fine; the writer handles it.
- **Pass each message once.** `--note` appends, so a note repeated on a re-run would appear twice.
  Re-runs after a pause are plain `storica develop <novel> <step>` without `--note`.
- **You may discuss when asked.** If the creator asks what you think, you can give your view, marked
  as yours, next to the editor's. The decision and the words that go into the note stay theirs.
- **Never read request files** (`_session/requests/`). The documents (`01_pitch.md` and so on) are
  what you read and relay.

## The loop

**1. Where are we?**

```bash
.venv/bin/storica develop <novel_dir>
```

It lists the steps with their version and status. Work on the first step that is not `approved`.
If there is no brief yet, stop and help the creator write `00_input/brief.yaml` (see an existing
novel for the format). The brief is the creator's text; don't invent it.

**2. Run a round of the step:**

```bash
.venv/bin/storica develop <novel_dir> <step>                    # first draft, or a re-run after a pause
.venv/bin/storica develop <novel_dir> <step> --note "<words>"   # the creator's new message
```

| Exit | Meaning | Do |
|---|---|---|
| `0` | The round is done (`ready`), or there's nothing to do (`waiting`) | Go to step 3 |
| `1` | Refused (unknown step, nothing to approve, notes not worked in yet) or no brief | Tell the creator the printed reason |
| `2` | Calls need answers | Dispatch every `[pending]` line (below), then run the same command **without** `--note` |
| `3` | An answer does not fit its schema | Delete the named response file and re-dispatch that call with the error appended to the prompt |

A round is two calls, the writer and then the editor, so expect two pauses.

**3. Present the document.** Read `<novel_dir>/<NN_step>.md` and give the creator, in their
language, briefly:

- the editor's summary;
- for options: each option's title, logline and "question of the book", two or three lines each,
  quoting the key German phrases. For a single pitch: what changed since the last version;
- the editor's recommendation;
- the editor's questions, verbatim (with a translation if the creator writes another language).

Then ask what they want: choose or combine options, change something, answer the questions, or
approve. Tell them once that they can also edit the file directly and just say "continue".

Stay faithful to the document. Don't smooth over weak spots the editor named, and don't add
qualities it doesn't have.

**4. Act on the answer.**

- Approval ("passt", "approve", "weiter", "go on"): `storica develop <novel_dir> <step> --approve`,
  then go to the next step, or tell the creator that this was the last step available so far.
- Anything else: step 2 with `--note "<their words, verbatim>"`.
- They edited the file themselves: step 2 without `--note`.

## Dispatching a pending call

Each `[pending]` line gives `model=`, `read=` and `write=`. Map `claude-opus-5` to `model: "opus"` and
`claude-sonnet-5` to `model: "sonnet"`. Spawn one `general-purpose` subagent per line, all in one
message, each with exactly this prompt:

> You are a single stateless model call inside an automated pipeline. You are not an assistant and
> there is no conversation.
>
> Read this one file: `<REQUEST_PATH>`
>
> It contains a system prompt, a user prompt, and — if the call expects structured output — a JSON
> schema. Obey it exactly as if it were the entire context of an API request, because it is.
>
> **Read no other file. Do not list directories, search the repo, or look at the novel's other
> documents.** The request already contains every fact you are permitted to use.
>
> Write your answer to: `<RESPONSE_PATH>`
>
> - If the request specifies a JSON schema: write **only** a single JSON object matching it. No
>   markdown fences, no commentary. Every required field must be present, and fields the schema
>   forbids must be absent.
> - If the request asks for text: write **only** the text as markdown. No preamble, no fences, no
>   notes about your choices.
>
> Do not ask questions and do not report back — writing the file is your entire output. When the
> file is written, your final reply is the single word `done`.

When every subagent has finished, run the step again without `--note`.

## After the session

`storica map <novel_dir>` shows every call of the room with its exact input and output, which is
useful for tuning the agents in `agents/`. Mention it when the creator wonders why an agent did
something.
