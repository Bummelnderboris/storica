# Novels

One folder per novel (`<slug>/`). Everything about a novel lives inside its folder; author assets are
shared and live in `/authors/`. Copy `_template/` to start a new novel.

## Per-novel layout

```
<slug>/
  00_input/                 # the front-door brief: spark, nudges, philosophical questions,
                            #   user Story-DNA, chosen author id. (Immutable ground truth once locked.)
  01_canon/
    story_model.json        # THE source of truth — structured, versioned, validated (see /DESIGN.md §4)
    history/                # every accepted canon version (audit trail)
  02_plan/
    macro_arc.json          # acts, turning points, per-character arcs, motif/promise schedule
    chapters/chNN.spec.json # per-chapter spec, elaborated just-in-time
  03_drafts/                # prose per chapter (+ scene units if used)
  04_trace/                 # every filled prompt + artifact per agent (the capture format)
  05_reports/               # checker verdicts, decisions.jsonl (binding rulings), quarantine, audit
  novel.md                  # assembled output
```

See `/DESIGN.md` for the pipeline that fills these. `_template/` is an empty skeleton to copy.

## Reference novel
- `der-chrachen/` — the **v1-format** capture from the 1:1 simulation run (Dürrenmatt). It predates
  this layout, so its internal structure is the old phase-numbered capture, kept as reference +
  evidence for the findings. See `der-chrachen/REFERENCE.md`.
