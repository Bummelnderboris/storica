# Archived docs

Point-in-time documents. They describe the v1 system and are **not maintained** — they are kept
because they record how the project got here. For what is true now, read [`/README.md`](../../README.md)
and [`/DESIGN.md`](../../DESIGN.md).

| Document | Written | What it is | Still true? |
|---|---|---|---|
| [`v1-state-of-the-repo.md`](v1-state-of-the-repo.md) | 2026-06-29, updated 2026-07-10 | Architecture audit of the v1 pipeline: how the 8 phases actually worked, which code was live and which was dead, plus the ten bugs found and fixed when the app was first run end to end | The v1 description and bug list are accurate. Its fix list is superseded — v2 answered it by redesigning rather than repairing |
| [`SETUP_REMAINING.md`](SETUP_REMAINING.md) | 2026-04 | A v1 setup to-do list | **No.** It was already wrong when written — it claims `story_dna` is unwired, but `api/projects.py` had wired it. Kept only so nobody rediscovers it and acts on it |
