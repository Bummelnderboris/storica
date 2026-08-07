# Pipeline Capture — Faithful 1:1 Simulation Run

This folder is a **full trace** of the Storica agent pipeline run by hand, agent by agent,
using the **exact prompt templates** in `backend/app/prompts/templates/` and the **exact
Dürrenmatt author profile**. For every agent we store:

- `prompt.md` — the **filled** system+user prompt the agent actually received (variables substituted)
- `artifact*.md` — the **output** that agent produced and handed to the next stage

The goal is to **inspect and tune the instructions**: read each `prompt.md` next to its
`artifact.md` and judge whether the instruction produced what we wanted.

---

## Inputs (the "Story DNA" a user would submit)

- **Author:** Friedrich Dürrenmatt · **Language:** German (`de`)
- **Genre:** Kriminalroman / Tragikomödie (philosophisch)
- **Chapters:** 3 · **Structure:** three-act
- **Spark:** In a remote Swiss mountain village, the one man who could prove the district
  doctor covered up a fatal malpractice 20 years ago dies in a car crash — and now lies on
  that doctor's table, awaiting the death certificate the doctor must sign.

Full DNA: [`inputs_story_dna.json`](inputs_story_dna.json)

## Fidelity notes (how faithful this is to the real app)

| Aspect | Real app | This run | Match? |
|---|---|---|---|
| Prompt templates | `templates/*.yaml` | same, filled verbatim | ✅ |
| Author profile | `duerrenmatt.yaml` | same | ✅ |
| Agent isolation | each agent = 1 stateless API call | each agent = 1 stateless sub-agent, prompt only | ✅ |
| Model split | Sonnet plan/critique · Opus prose | same | ✅ |
| Output threading | truncated summaries between phases | same truncations | ✅ |
| Orchestration code | Python (`generate_story.py`) | done by hand | ⚠️ code path NOT exercised (JSON parsing, story-bible **merge/dedup bug**, DB, cost meter). Use run mode (A) to test those. |

## Pipeline order & index

| # | Agent | Model | Instruction (prompt) | Artifact |
|---|---|---|---|---|
| 0 | Author Loading | — (no LLM) | — | [style guide](00_author_loading/artifact_style_guide.md) |
| 1 | Topic Explorer | Sonnet | [prompt](01_topic_exploration/prompt.md) | [artifact](01_topic_exploration/artifact.md) |
| 2 | Thesis Developer | Sonnet | [prompt](02_thesis/prompt.md) | [artifact](02_thesis/artifact.md) |
| 3 | Character Deriver | Sonnet | [prompt](03_characters/prompt.md) | [artifact](03_characters/artifact.md) |
| 4 | Story Architect | Sonnet | [prompt](04_architecture/prompt.md) | [artifact](04_architecture/artifact.md) |
| 5 | Blueprint Planner ×3 | Sonnet | `05_blueprints/chNN_prompt.md` | `05_blueprints/chNN_artifact.md` |
| 6 | Prose Room ×3 | Sonnet+Opus | `06_prose/chNN/` (reason→write→critique→[revise]→consistency) | per-step files |
| 7 | Final Consistency | Sonnet | [prompt](07_final_consistency/prompt.md) | [artifact](07_final_consistency/artifact.md) |

Assembled novel: [`novel.md`](novel.md) · Findings log: [`FINDINGS.md`](FINDINGS.md) · Divergence: [`DIVERGENCE.md`](DIVERGENCE.md) · Bible state: [`story_bible_state.json`](story_bible_state.json)

_Status: **RUN COMPLETE.** 22 agent calls: 5 planning + 3 blueprints + 3 chapters ×(reason→write→critique→[revise]→consistency) + Ch2 reviser. Model split Sonnet/Opus as in the app._

---

## Synthesis — what the run proved

**The prose is genuinely good.** Opus produces on-voice, structurally coherent Dürrenmatt at the sentence level; the planning chain (topic→thesis→characters→architecture→blueprints) is high quality. The design's creative core works.

**The failure mode is canon integrity, and it cascades.** The story bible is seeded from *prose*, not from the Phase-3 character sheet. So:
1. A blueprint invented a wrong fact (Berta as wife — F6).
2. The Writer invented another (Rutz the priest → a creditor — F9); the critic couldn't catch it because the Ch1 bible was empty (F8/F9).
3. The Guardian **canonized** the error into the bible (F10).
4. The Ch2 Reasoner hit the contradiction and **fabricated a bridging fact** to paper over it (F11).
5. The Ch2 critic (now with a populated bible) finally caught it → **the reviser fired** — but, pointed at the *corrupted* bible, the reviser **amplified** the damage (renamed the victim, changed the cause of death, split a character — F12).

**Your two headline questions, answered with data:**
- *Revision loop* — not universally dead weight (it fired in Ch2), but it only ever triggers on **story-consistency** failures, which are mostly the pipeline's own bible-drift. On clean canon (Ch1, Ch3) competent drafts score ~7.8 and pass while the critic's real editorial notes are discarded. See F8.
- *Bible bloat/de-dup* — root-caused to `story_bible.py`: character keys dedup only on exact string match (no variant normalization) and timeline appends unbounded (F7). **Confirmed fixable**: when the guardian was handed the key list + a reuse instruction (Ch3), character fragmentation went to zero.

## Prioritized fix list (code-mapped)

| Pri | Fix | Where | Kills findings |
|---|---|---|---|
| **1** | **Seed the story bible from the Phase-3 character sheet BEFORE blueprinting**, and thread canon into blueprint + critic + reviser. Make the Guardian check "contradicts canon?" not just "extract new facts." | `generate_story.py` (bible init at phase 5); `phase7_consistency/*` | F6, F9, F10, F11, F12 |
| **2** | **Pin bible keys**: pass the existing key list to the Guardian and force reuse; normalize variants; **dedup the timeline**; cap characters shown in the prompt. | `phase7_consistency/story_bible.py:111-155`, `to_prompt_summary` | F7 |
| **3** | **Re-gate the critique**: raise threshold to ~8.5 OR fire the reviser if any single category < 8 OR make critique skippable/cheaper. Never let the reviser "repair" toward a mutable bible — resolve to ground truth or halt. | `phase6_prose/loop.py`, `values.py` thresholds | F8, F12 |
| **4** | **Collapse the double LLM call** in planning agents (generate + JSON-extract) into one native structured-output call; treat parse failure as error, not silent placeholder. | `phase1_topic/explorer.py` (& siblings) | F3 |
| **5** | Thread a real prior-chapter summary instead of `raw_blueprint[:800]`; wire `subgenres` into the topic prompt (or drop it). | `generate_story.py` blueprint loop; `topic_exploration.yaml` | F5, F1 |
