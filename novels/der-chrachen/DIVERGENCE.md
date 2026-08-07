# DIVERGENCE — what the readable novel changed vs. what the pipeline would have shipped

`novel.md` is the **readable** assembly. The current Storica pipeline, run faithfully, would NOT
produce that text — it would ship a canon-corrupted version. This file records exactly where the
readable novel departs from the pipeline-faithful output, so nothing is hidden.

## 1. Chapter 2 — we used the PRE-revision draft; the pipeline would ship the REVISED one

The Ch2 critic scored the first draft **5.8 → REVISE** (it caught the Rutz contradiction the
pipeline itself created). The reviser then ran and, obeying the critique against a *corrupted*
bible, produced `06_prose/ch02/4_revised.md`, which the loop would return as final. That revised
text introduced **worse** corruptions:

| Element | Pre-revision (used in novel.md) | Pipeline-shipped revision (4_revised.md) |
|---|---|---|
| Victim's name | Klara Vogel | **"Anna Vogel, geb. Aebi"** (invented) |
| Cause of death | Fall in the Chrachen, no autopsy | **Poisoning** — a stomach "Präparat", a Sektionsbefund (contradicts Ch1) |
| Stettler's role | Amtsarzt (physician) | **Amtsstatthalter** (magistrate) |
| Rutz | One man (priest, also owed money) | **Split into two**: a creditor + a separate unnamed priest |
| Berta | Widow, in her own home | **In Feuz's home as his domestic** |

We used the pre-revision draft because it stays coherent with Ch1 and Ch3. **The pipeline as it
stands today would have shipped the right-hand column.** (See FINDINGS F12.)

## 2. Chapter 3 — we threaded CORRECTED canon into the bible

By the end of Ch1, the guardian had canonized "Rutz = creditor" (FINDINGS F10), overwriting the
Phase-3 truth (Rutz = priest). Threaded faithfully, Ch3 would have inherited that wrong fact.
For the readable novel we instead threaded the **corrected** canon (Rutz = priest, Stettler =
Amtsarzt, fall/no-autopsy, victim = Klara Vogel) — i.e. what a properly **seeded** bible (the F6/F7
fix) would have carried. Ch3 then came out clean (critic 7.8, guardian 0 contradictions).

## 3. One residual seam left in Chapter 1 (unedited)

Ch1's prose calls Rutz a creditor waiting in the hallway ("dem der Tote Geld geschuldet hatte").
That line is the origin of the whole cascade. We left it **as written** (only footnoted in
`novel.md`) so the artifact honestly shows where the drift began.

---

### The one-line takeaway
The pipeline's creative output is excellent sentence-by-sentence, but it has **no ground-truth
canon**: the bible is seeded from prose (not from the Phase-3 character sheet), so a single early
slip becomes permanent, the critic can't catch what the bible doesn't know, and the reviser
"repairs" toward the corrupted bible — amplifying the error. Fixing the bible (seed from Phase 3,
pin keys, feed canon to critic+reviser) removes the root cause behind F6, F9, F10, F11, and F12 at once.
