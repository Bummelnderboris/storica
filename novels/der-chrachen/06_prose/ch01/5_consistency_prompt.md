# FILLED PROMPT — Phase 6, Ch1, Step 5: Consistency Check / Bible Update  (model: Sonnet)

> Template: `consistency_check.yaml`. `{chapter_index}` = 1. `{chapter_prose}` = full Ch1 draft.
> `{story_bible}` = "{}" (empty). Output `updates[]` are merged via `apply_updates()`; character
> `key` becomes the dict key (F7: exact-string keying, no variant normalization).
> No Reviser step ran (critique PASSED), so this operates on the original draft.

## SYSTEM
You are a continuity editor ensuring story consistency.
Your job: (1) check the new chapter against the existing story bible, (2) identify inconsistencies,
(3) extract new facts to add to the story bible. Be thorough but not pedantic.

## USER
[Chapter 1 prose (full) + current story bible "{}" passed verbatim.]
Tasks: Consistency Check (character/setting/plot/object); Issues Found (severity + fix);
Story Bible Updates as structured data (new characters name+description+role; new locations;
objects; timeline events; character developments; foreshadowing).
