# Novels

One folder per novel (`<slug>/`). Everything about a novel lives inside its folder; author assets are
shared and live in `/authors/`. Copy `_template/` to start a new novel.

## Per-novel layout

```
<slug>/
  00_input/brief.yaml       # the front-door brief: author_id, spark, thoughts, question_lines,
                            #   nudges, forbidden, language, chapter_count, title_hint.
                            #   Immutable ground truth once created.
  01_canon/
    story_model.json        # THE source of truth — structured, versioned, validated (see /DESIGN.md §4)
    history/                # every accepted canon version (audit trail)
  02_plan/
    macro_arc.json          # acts, turning points, per-character arcs, motif/promise schedule
    chapters/chNN.spec.json # per-chapter spec, elaborated just-in-time
  03_drafts/                # prose per chapter (+ scene units if used)
  04_trace/                 # every filled prompt + artifact per agent (the capture format)
  05_reports/               # decisions.jsonl (binding rulings), quarantine.jsonl (with releases),
                            #   state.json — each created when first needed
  06_session/               # --driver replay only: the request/response cache. Do not delete
  novel.md                  # assembled output, quarantined chapters excluded
```

See `/DESIGN.md` for the pipeline that fills these. `_template/` is an empty skeleton to copy.

## Novels here
- `der-chrachen/` — the **v1-format** capture from the 1:1 simulation run (Dürrenmatt). It predates
  this layout, so its internal structure is the old phase-numbered capture, kept as reference +
  evidence for the findings. See `der-chrachen/REFERENCE.md`.
- `der-chrachen-v2/` — the same story under the v2 pipeline: the P6 run, finished 2026-09-22 under the
  replay driver. Its `06_session/` is the run itself; see `/docs/archive/p6-handoff.md`.
- `der-chrachen-v3/` — the same brief again, developed in the **writers' room** (`storica develop`,
  the `/develop` skill) with the creator steering. Its layout is the room's: step documents at the
  top (`01_pitch.md`, ...), earlier versions in `_history/`, calls in `_trace/` and `_session/`.
