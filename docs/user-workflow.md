# The user workflow: what it is like to write a book with Storica

**Draft, 2026-09-28.** It will be revised after the first session test with a first-time user. It
describes the product, not today's terminal session. Where the engine already exists, the section
says so.

## Who it is for

Someone who wants a book and knows nothing else: not how novels are built, not the vocabulary of
writing, not the authors in the library, not how Storica works. They know what kind of book they
would enjoy, and they will recognise it when they see it.

The first test showed what happens otherwise. The story editor asked whether the doctor's "inner
decision" should "carry the first chapter", and whether the ending should be "as in B and C". The
creator could not place any of it.

## Principles

1. **Assume the user knows nothing.** Every screen makes sense to a first-time reader.
2. **Show choices, not questions.** Each question offers two or three concrete possibilities, each
   with one sentence on what it would mean for the book, and always "you decide".
3. **Short first, full text on demand.** A stage fits into a minute of reading. The full document
   is one click away, and it is also editable.
4. **The user decides, the agents write.** Nothing the user did not choose or hand over enters the
   book. Their words are kept as decisions, and every agent after them reads those decisions.
5. **Nothing is lost.** Every version is kept, and the user can go back to any of them.

## The stages

| Stage | The user sees | The user can | Agents | Engine today |
|---|---|---|---|---|
| **Start** | A short conversation: what the book should be about ("no idea yet" is fine), any must / must not, language, whose way of telling (one plain sentence per author), a working title | Answer in their own words, skip anything | none | `/develop` step 0, then `storica new` |
| **Pitch** | Three option cards: what the book is about and what it would be like to read; the editor's view in a sentence each; at most two choice questions | Pick, combine, comment, answer a question, "you decide", approve | pitch writer, story editor | **built**: `storica develop <novel> pitch` |
| **Characters** | One card per main character: who they are, what they want, what they fear, how they talk (a line or two) | Comment per card, add or remove a person, approve | character developer, story editor | R3 |
| **Storyline** | A diagram of people × chapters (who does what, where), plus one readable page | Comment on a block in the diagram or on the page, approve | plot architect, story editor | R3 |
| **Chapter plan** | Per chapter, one line per scene, with the point of each scene for the reader | Skim; object where a scene has no point; approve | chapter planner, story editor | R3 |
| **Writing** | Per chapter, a digest: what happens in five lines, the key conversations quoted, the moment that carries the chapter, threads opened and closed, the first reader's concerns. The full chapter on demand | Steer with notes, or "go on" | editor's notes, writer, first reader, continuity check, bible keeper | R4 |
| **The book** | The finished text, and a readable account of how it came about: what was decided, by whom, and what changed | Download, go back to any stage | none | R4 |

A **flow** decides which of these stages are worked on together and which only report back. For
example, "fast draft" writes all chapters straight through and shows one digest at the end (R5).

## Time and cost

Measured on the first pitch round: two calls (writer and editor, both on Opus). That is roughly
3,000 to 6,000 input tokens and 2,000 to 3,000 output tokens per call, so **about $0.20 per pitch
round** at the prices in `src/storica/llm.py`, and a minute or two of waiting.

A whole book is an estimate, not a measurement. P6 made 219 calls at an average input of about
8,000 tokens, which comes to **roughly $10–30 for three chapters**. The room should spend less on
checking and more on planning. Every round the user asks for adds about $0.20 during planning, and
more per chapter.

## Interfaces

The stages and documents are the same in every interface; only the surface changes.

1. **A terminal session (now).** A Claude Code session hosts the room (`/develop`) and answers every
   agent call with a fresh subagent, on the user's subscription. It is good for testing the flow,
   but it is not something a first-time user would open.
2. **A web app with the API (the target).** One page per stage, cards, buttons and comments. It
   calls `storica.room` directly (`advance`, `add_note`, `approve`) with the Anthropic driver in
   `src/storica/llm.py`. It needs an API key, and the API path has never run: `tools/smoke_test_api.py`
   comes first.
3. **A page hosted on claude.ai (unchecked).** Such pages may be able to call Claude themselves,
   possibly without an API key of the user's own. Whether that holds up for several agents and long
   texts has to be checked before anyone relies on it.

## Open questions for after the session test

- Is three options the right number, or is it too much to read?
- Do users want to talk ("make the doctor younger") or click (cards and choices)? Probably both;
  the test will show which comes first.
- When does a user want to see the full text rather than the digest?
- How much of the author library should a first-time user see at all?
