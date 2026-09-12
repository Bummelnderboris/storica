# Authors library

Reusable author assets, shared across all novels. One folder per author (`<author_id>/`).
A novel references an author by id; nothing here is novel-specific.

```
<author_id>/
  profile.yaml        # philosophy, style, patterns, critique rubric  (the machine-read spec)
  question_lines.md   # the recurring questions/obsessions this author "has" — drives CONCEPTION
  nudges.md           # how to steer toward / away; do & don't for prose + checkers
  impression.md       # what it feels like to read them (human-facing orientation)
  examples/           # annotated voice samples: the text + why it works
```

**Roles in the v2 pipeline (see /DESIGN.md):**
- `question_lines.md` + `profile.yaml` feed **Stage 1 Conception** — the author is a *generative
  driver*: their obsessions shape *which story gets told*, not just its style.
- `nudges.md` + `profile.yaml.critique_rubric` feed the **Author-Voice checker** (§6).
- `examples/` are **not read by the pipeline today**. `authors.py` loads `profile.yaml`
  (`metadata.name`, `metadata.primary_language`, `philosophy.worldview`, `central_obsession`) plus
  `question_lines.md`, `nudges.md` and `impression.md`, and nothing else. The examples are kept for
  the human writing a profile, and for a future exemplar-grounded voice checker.

> This library is the single source for author assets. The v2 pipeline reads it directly
> (`--authors` defaults here); the v1 copies under `legacy/backend/authors/profiles/` are archived
> and no longer read by anything.
