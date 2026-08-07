# ARTIFACT — Phase 6, Ch3, Step 5: Consistency Check + Bible Updates (Sonnet)

> ✅ F7 FIX CONFIRMED (for characters): instructed to reuse existing keys, the guardian reused them
> EXACTLY — "Dr. Konrad Stettler", "Rutz", "Berta Aebischer", "Melchior Aebischer", "Klara Vogel".
> No character-key fragmentation. So passing the current key list + a reuse instruction solves F7 for characters.
>
> ⚠️ BUT drift persists elsewhere:
> - New OBJECT keys spawned for things arguably already tracked: "Akte 'Vogel, Klara' (alte Akte)"
>   (vs existing "Eichenschrank"/"Der Totenschein"); the guardian itself flagged a Bestattungsdokument-
>   vs-Totenschein ambiguity.
> - New LOCATION keys: "Aktenkeller", "Kirche (Aussenbereich, Lauenegg)".
> - TIMELINE appended 5 more events → 10 total, still unbounded (no dedup).

## PART A — Consistency Check (no contradictions; notes)
1. "Pfarrer Rutz" = title only; correctly kept under key `Rutz` (role in description). ✅
2. Bestattungsdokument vs Der Totenschein — possible object fragmentation; guardian treats them as same for now.
3. 20-year anchor: Stettler has held the post ≥20 years — reconcile with any age detail.
4. Marolf absent (informational).
5. Signing-scene location unnamed (plausibly Feuz's Amtsstube).

## PART B — Updates (characters reuse exact keys; new object/location keys added)
Characters updated (keys reused): Dr. Konrad Stettler, Martin Feuz, Berta Aebischer, Melchior Aebischer, Rutz, Klara Vogel.
New locations: `Aktenkeller`, `Kirche (Aussenbereich, Lauenegg)`. New object: `Akte 'Vogel, Klara' (alte Akte)`.
Timeline +5 (now 10). Foreshadowing +5.
