# Calibration findings — Canon-Consistency checker

Run: `.venv/bin/python tools/calibrate_checkers.py`. Method and answer key are in that file;
raw verdicts are in `results/`, the exact prompts in `06_session/requests/`.

**Read the caveat first.** The arm study (C1–C3) is n=1 per cell. The reliability study (C4, C5) is
n=5 per case, on two cases. Neither is large, and two of the original n=1 findings turned out to be
artefacts once resampled — see C5. Rates below are indicative, not established.

---

## C1 — The reference canon contains the very bridging fact FINDINGS condemns · **critical**

`novels/der-chrachen/01_canon/story_model.json` records:

```json
"rutz": { "facts": { "relation": "old friend of Stettler; Melchior owed him 300 francs privately" } }
"relationships": [ { "a": "rutz", "b": "melchior", "type": "creditor_of" } ]
```

So Rutz **is** a creditor in canon. The v1 prose calling him one is therefore not a contradiction,
and the checker was right to pass it in both arms.

But "Rutz is a priest AND a private creditor" is precisely the invented reconciliation that
[F11](../novels/der-chrachen/FINDINGS.md) identifies as canon corruption — the bridging fact the ch2
reasoner fabricated to paper over a contradiction it should have flagged. It has been written into
the file that is supposed to be ground truth.

`DESIGN.md` §4 carries it too, in the worked example that illustrates what canon should look like:

```jsonc
"rutz": { "facts": { "relation_to_protagonist": "old friend + private creditor" } }
```

**The mechanism:** this canon was reconstructed *after* the v1 run, by someone reading the v1
output. Ground truth derived from corrupted prose inherits the corruption — which is the v1 failure
mode exactly, performed by a human instead of an agent, on the artifact built to prevent it.

**Consequences.**
1. This file cannot be used as ground truth for anything. It is evidence, not canon.
2. `novels/der-chrachen-v2/` must build canon from the brief alone. It currently does — the brief is
   a translation of the v1 *inputs*, not of the v1 outputs — so P6 is unaffected. Keep it that way.
3. DESIGN §4's example should be corrected, or it teaches the bug.
4. **The design needs a rule it does not have:** canon may only be authored from the brief and from
   validated upstream canon — never from prose, and never reconstructed after the fact. Principle 1
   says prose is never re-parsed as truth, but says nothing about *humans* doing it.

---

## C2 — No overfitting gap · good

The checker's rubric names this book's failures as examples, so every case ran twice: `shipped`, and
`generic` with every der-chrachen specific replaced by a neutral phrasing (no "priest", "creditor",
"widow", "housekeeper", "cause of death").

```
shipped  4/5 planted errors caught
generic  4/5 planted errors caught
```

Identical. The catches survive removal of the answer key, so the checker is **detecting
contradiction, not recognising this book**. This is the result that predicts the next novel, and it
is the strongest evidence so far that the canon-armed-checker idea works at all.

Caught in both arms: victim renamed (Klara Vogel → "Anna Vogel, geb. Aebi"), cause of death changed
(fall → poisoning), office changed (Amtsarzt → Amtsstatthalter), Berta moved from widow to domestic.
These are the F12 cascade — the failures that made the v1 book unshippable.

---

## C3 — No false positives on the control · good

`ch03_draft` was written against corrected canon and the v1 guardian found nothing wrong with it.
Both arms returned `pass` with zero issues.

This matters as much as C2. A checker that flags everything scores perfectly on planted errors and
is useless in a pipeline, because every chapter would enter a repair loop and never leave. The
checker also correctly filed speculative-but-harmless detail as **warnings** rather than blocking
issues (an invented brass drawer-handle, an unconfirmed job title) — the distinction the rubric asks
for, applied correctly without prompting.

---

## C4 — The gate is not deterministic · **high** · *resolved: majority sampling*

First seen at n=1: `ch01_draft / shipped` answered twice gave `revise` (3 issues, one blocking) and
then `pass` (0 issues). So the flip rate was measured properly — the same prompt drawn five times per
case, nothing varying but sampling (`--reliability 5`, results in `results/reliability/`):

| Case | Decisions across 5 draws | Draws that blocked |
|---|---|---|
| `ch02_revised` (5 planted errors) | revise ×5 | **5/5** |
| `ch03_draft` (clean control) | revise, pass, pass, pass, pass | **1/5** |

**The checker is decisive about real breakage and noisy about clean text.** That asymmetry picks the
aggregation rule, and it rules out the intuitive one:

| rule | blocks clean text | catches broken text |
|---|---|---|
| single draw (k=1) | 20% | reliably |
| **union** over k=3 ("any draw blocks") | **49%** | reliably |
| **majority** over k=3 | **10%** | reliably |

Union-blocking multiplies the noise it is meant to average out. A pipeline that sends half its good
chapters into repair burns budget rewriting prose that was already fine — and repair is the step that
makes prose grey (DESIGN §5.1). Majority beats even a single draw on false positives while losing
nothing on recall, because broken text blocks in every draw.

**Implemented** as `ConsensusProseChecker` (`checkers/consensus.py`), default `--checker-samples 3`,
applied to canon-consistency only. One deliberate asymmetry: **majority decides, union reports** —
once a unit is judged broken, the repair agent sees every issue any draw found, not only the ones two
readers happened to agree on. That is what recovers C5 below.

Still true and worth remembering: **a "pass" is weaker evidence than it looks.** The final auditor
should not treat per-chapter passes as settled.

---

## C5 — ~~One real miss~~ · **overturned by the reliability run**

Originally recorded as the checker's one genuine failure: `F12_rutz_split` — the reviser splits Rutz
into two people, a creditor plus a separate unnamed priest — was missed in both arms.

**It was sampling noise.** Across five draws it was caught in **4/5**. The single draw scored in the
arm study happened to be the one miss, and one draw was never enough to tell a capability gap from a
bad roll. Per-error detection over five draws:

| planted error | caught in |
|---|---|
| victim renamed | 5/5 |
| cause of death | 5/5 |
| Stettler's office | 5/5 |
| **Rutz split** | **4/5** |
| Berta's role | 5/5 |

Union over the five draws catches **5/5** planted errors, against 4/5 for the single draw that
produced the original C2 number. So the checker's real recall is higher than first reported, and the
majority-decides/union-reports rule in C4 is what realises it.

The lesson is methodological and worth more than the finding it replaced: **at n=1 a miss and an
unlucky draw are indistinguishable.** Two of this document's original findings (this one, and C1's
"missed F9") were artefacts rather than defects.

The identity split/merge rubric axis was added anyway — it costs nothing, the failure is real, and it
is the kind that is invisible in one chapter and fatal across ten.

---

## What this changes

| Finding | Action |
|---|---|
| C1 | Ground-truth rule: canon is authored from the brief, never reconstructed from prose. Fix DESIGN §4's example. Never seed a run from `der-chrachen/01_canon`. |
| C2 | Keep the checker. The approach is validated as far as n=1 can validate it. |
| C3 | Keep the warning/blocking distinction; it is working. |
| C4 | **Done.** Majority-of-3 sampling on canon-consistency (`--checker-samples`), majority decides / union reports. |
| C5 | Split/merge identity axis added. Recall is better than first reported; the "miss" was a bad roll. |

The headline: the checker layer is worth keeping, and **the data it was tested against was the
broken part** — both the reference canon (C1) and, twice, this document's own answer key (C1, C5).
That is a much better thing to learn from twenty calls than from a finished book.

## Still open

- **Recall is measured on five errors in one chapter of one book.** Every planted error here is a
  *fact* changing. Nothing tests whether the checker catches a contradiction of tone, motive, or
  implication — and those are likelier failure modes now that facts are structured.
- **Only canon-consistency has been calibrated.** Micro-sense, voice and vitality are unmeasured, and
  vitality is the one most likely to be generous, because LLM judges reward fluency and fluency is
  exactly what a dead chapter has.
- **The control is one clean chapter.** A 20% false-positive rate estimated from 5 draws of 1 chapter
  has a wide interval; if it is really 35%, majority-of-3 costs ~28% and the rule needs revisiting.
- **Sampling was measured on a chapter-level check.** Scene-level checks see less context and may be
  noisier still.
