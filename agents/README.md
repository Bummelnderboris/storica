# Agents

Every model call Storica makes is one of the agents in this folder. Each file holds everything that
agent is told, plus a short description of how it is wired in. To change how an agent behaves, edit
its file. You don't need to touch the Python.

To see them all at once, with what each one actually received in a run:

```bash
.venv/bin/storica map                          # the agents and their instructions → ./agent_map.html
.venv/bin/storica map novels/der-chrachen-v2   # plus every call of that run → 05_reports/agent_map.html
```

## What a file contains

```
---
id: voice                      the name the code asks for (must match the file name)
name: Author-voice reader
model: sonnet                  the model this agent runs on by default
family: judge                  maker · judge · extractor · arbiter
phase: scene                   where it sits in the map: plan · scene · chapter · book · any
order: 62                      its position within the map
step, fires, reads, writes,    plain-language description, shown on the map
authority, also_used_as
input_built_in                 where the code assembles this agent's input (the per-call prompt)
trace                          stage-name patterns, used to find this agent's calls in 04_trace/
---
You are an Author-Voice checker ...          ← the system prompt, exactly as sent

<!-- rubric -->
Judge in this order: ...                     ← a named section the code places inside the prompt
```

- **The body up to the first `<!-- name -->` line is the system prompt**, byte for byte. Only the
  file's final newline is dropped.
- **Named sections** are instructions the code puts inside the per-call prompt: a reader's rubric,
  the writer's "before you write" block. Each starts with a blank line followed by
  `<!-- name -->` on its own line. The code asks for a section by its name, so rename a section only
  together with the code that uses it.
- **`{{include: invention-policy}}`** is replaced by `_shared/invention-policy.md`. That block is read
  by both the writer and the micro-sense reader that judges the writer, so it lives in one place.
- Only `id`, `name`, `model` and the text are used by the pipeline. The other frontmatter fields are
  descriptions for people and the map, and they can drift from the code. `input_built_in` tells you
  where to check.

## What is still in the code

The **per-call prompt**, meaning which canon, plan and prose each agent is handed and in what order,
is assembled by the functions named in `input_built_in`. The map shows the result for every call.
Moving the templates for that assembly into files is later work.

## Editing an agent changes the calls

The replay driver matches each recorded answer to the exact text of the call. If you edit an agent's
instructions, every call that agent makes becomes a new call, and a replay run stops and asks for an
answer to it. That's intended: new instructions deserve a new answer. It also means you can check
that a change touched nothing else. Replay a finished run on a copy of its folder, and only the edited
agent's calls should be asked again.
