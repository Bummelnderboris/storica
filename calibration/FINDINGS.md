# Calibration findings — Canon-Consistency checker

Run: `.venv/bin/python tools/calibrate_checkers.py`. Method and answer key are in that file;
raw verdicts are in `results/`, the exact prompts in `06_session/requests/`.

**Read the caveat first.** Every cell is n=1 — one verdict per case per arm. C4 below shows the
same prompt producing two different gate outcomes, so treat all of this as a smoke test that found
real defects, not as a measurement of a rate.

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

## C4 — The gate is not deterministic · **high**

`ch01_draft / shipped` was answered twice, same prompt, same model, two fresh agents:

| Run | Decision | Issues |
|---|---|---|
| 1 | `revise` | 3 — including one **blocking** timeline contradiction (`t9`, who files the Aebischer case) |
| 2 | `pass` | 0 |

One run blocks the chapter and sends it to repair; the other ships it. Both are defensible readings,
and run 1 found a genuine contradiction that is not in the answer key at all — so this is not a
"wrong" answer, it is variance in what a reader notices.

That is tolerable in a human editor and corrosive in an automatic gate. It means a chapter's fate
depends on which sample it drew, and that a passing run tells you much less than it appears to.

**Implications for the design.**
- Blocking decisions should not rest on a single sample. Cheap options: run the consistency checker
  k times and block on any blocking issue found by any run (raises recall, costs k calls), or
  require agreement before *passing* rather than before failing.
- A "pass" is weak evidence. The final auditor should not treat per-chapter passes as settled.
- Quantify before tuning: this is n=1: measure the flip rate on a real book before choosing k.

---

## C5 — One real miss, and it is the subtle kind · medium

`F12_rutz_split` — the reviser splits Rutz into two people, a creditor plus a separate unnamed
priest — was **missed in both arms**.

Partly downstream of C1: since canon blesses "priest and creditor as one man", a reader has to
notice that the prose has quietly made them *two*, which is a harder judgement than a changed fact.
It is also the failure that is most specific to long-form: a character silently fissioning is
invisible in one chapter and fatal across ten.

Worth a rubric axis of its own — *one canon id, one person; check that the prose has not split or
merged anyone* — since the existing axes are all about attributes changing, not about identity
count.

---

## What this changes

| Finding | Action |
|---|---|
| C1 | Ground-truth rule: canon is authored from the brief, never reconstructed from prose. Fix DESIGN §4's example. Never seed a run from `der-chrachen/01_canon`. |
| C2 | Keep the checker. The approach is validated as far as n=1 can validate it. |
| C3 | Keep the warning/blocking distinction; it is working. |
| C4 | Do not trust a single-sample gate. Decide the sampling policy before P6, or P6's result is unreadable. |
| C5 | Add a split/merge identity axis to the consistency rubric. |

The headline: the checker layer is worth keeping, and **the data it was tested against was the
broken part**. That is a much better thing to learn from ten calls than from a finished book.
