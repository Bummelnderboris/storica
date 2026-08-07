# ARTIFACT — Phase 6, Ch1, Step 5: Consistency Check + Bible Updates (Sonnet)

> ⚠️ CASCADE (see FINDINGS F10): the guardian had no prior canon, so it recorded whatever the
> prose said — including the Writer's error, canonizing **Rutz as "Local creditor"** rather than
> the village **priest**. This wrong fact now enters the bible and will be threaded into Ch2/Ch3.

## PART A — Consistency Check
No cross-chapter contradictions (bible was empty). Minor internal notes:
1. **Unclear speaker attribution (minor)** — some interrogation lines untagged; reads as intentional terseness. Bible should record Feuz as the default examining magistrate in interviews.
2. **Timeline gap (minor)** — how/when the body was first spotted before dawn is unstated; watch against Berta's "yesterday after the meal."
3. **Forensic tension (flag, not error)** — physical exam + pre-decided verdict + declined autopsy reads as deliberate cover-up setup; reconcile if a later chapter reveals a different cause of death.
No critical inconsistencies. **(Note: it did NOT flag the Rutz priest/creditor problem — it had no canon to flag it against.)**

## PART B — Story Bible Updates (canonical keys emitted)
Characters: `Melchior Aebischer`, `Dr. Konrad Stettler`, `Martin Feuz`, `Berta Aebischer`, `Marolf`, **`Rutz` (recorded as creditor — WRONG)**.
Locations: `Der Chrachen`, `Lauenegg`, `Amtsraum (unheated examination room)`, `Feuz's Amtsstube`.
Objects: `Der Totenschein`, `Narbe am Kinn`, `Genagelte Bergschuhe`, `Eichenschrank`.
Timeline: 5 events (night fall → dawn retrieval → morning exam → identification → afternoon filing).
Foreshadowing: 6 items (Berta's hesitation; cost-driven verdict; debts as motive; Rutz's stake; Berta's "dass er einmal hinunterfällt"; Feuz's double-underlines).

Full JSON persisted in `../../story_bible_state.json` (as applied after Ch1).

### Name-key note (F7 test)
Ch1 keys are clean and canonical ("Dr. Konrad Stettler", not "Stettler"). The F7 fragmentation
test is whether **Ch2's** guardian reuses these exact keys or emits variants. Watch `story_bible_state.json`.
