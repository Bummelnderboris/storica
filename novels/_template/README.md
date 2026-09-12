# Novel skeleton (template)

Copy this folder to `novels/<slug>/` to start a new novel. Folders map to the v2 pipeline (`/DESIGN.md`):

| Folder | Holds | Written by |
|---|---|---|
| `00_input/` | `brief.yaml`: author_id, spark, thoughts, question_lines, nudges, forbidden, language, chapter_count, title_hint (immutable once created) | creator |
| `01_canon/` | `story_model.json` (source of truth) + `history/` | Stages 1–2, Reconcile |
| `02_plan/` | `macro_arc.json`, `chapters/chNN.spec.json` | Stages 3–4 |
| `03_drafts/` | prose per chapter | Stage 5 |
| `04_trace/` | filled prompts + artifacts per agent | all stages |
| `05_reports/` | `decisions.jsonl`, `quarantine.jsonl`, `state.json` — created when first needed | verification layer |
| `06_session/` | request/response cache, `--driver replay` only | replay driver |
| `novel.md` | assembled output, quarantined chapters excluded | assembly |

`storica new novels/<slug> --author <id>` creates this skeleton and the brief for you; see
`novels/der-chrachen-v2/` for a folder mid-run.
