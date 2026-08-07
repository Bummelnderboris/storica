# Novel skeleton (template)

Copy this folder to `novels/<slug>/` to start a new novel. Folders map to the v2 pipeline (`/DESIGN.md`):

| Folder | Holds | Written by |
|---|---|---|
| `00_input/` | brief: spark, nudges, questions, Story-DNA, author id (immutable once locked) | creator |
| `01_canon/` | `story_model.json` (source of truth) + `history/` | Stages 1–2, Reconcile |
| `02_plan/` | `macro_arc.json`, `chapters/chNN.spec.json` | Stages 3–4 |
| `03_drafts/` | prose per chapter | Stage 5 |
| `04_trace/` | filled prompts + artifacts per agent | all stages |
| `05_reports/` | checker verdicts, `decisions.jsonl`, quarantine, final audit | verification layer |
| `novel.md` | assembled output | assembly |
