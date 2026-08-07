# Storica — Architecture & State Report

> **UPDATE (2026-07): the app has now actually been run.** I booted it locally on
> SQLite and drove it via the API (register → login → create project → start pipeline).
> It now runs through auth, project creation, and pipeline phases 0–1, failing only at
> the first Claude call because no API key is set. Getting there required fixing a chain
> of real bugs left by the WIP rewrite (the storage adapter never matched the ORM models).
> See **§0 — What actually happened when we ran it** below. Note: my earlier "likely
> sync/async bug" in §5.4 was **wrong** — the sync/async split is deliberate and correct.

---

## 0. What actually happened when we ran it

**Verified working (SQLite, no Docker needed):** app import, all migrations' schema (built
from ORM models via `create_all`), `register` → `login` → `create project` → `list`,
`authors` endpoints, pipeline `start` + `status`, WebSocket event emission, phase 0
(author loading), and phase 1 reaching the Claude API. Final blocker is only the missing
`ANTHROPIC_API_KEY`.

**Bugs found and fixed to get there:**

| # | File | Bug | Fix |
|---|------|-----|-----|
| 1 | `alembic/env.py` | `settings.database_url` (lowercase) with `case_sensitive=True` → AttributeError | Use `settings.DATABASE_URL` |
| 2 | `alembic/env.py` | Fed sync URL into async engine | Wrap with `_get_async_url()` |
| 3 | `alembic/versions/003_*` | `down_revision='002_add_cost_fields'` but rev id is `'002'` → broken chain | Set to `'002'` |
| 4 | deps | `greenlet`, `asyncpg`, `psycopg2` missing on py3.13 | installed (should be pinned in requirements) |
| 5 | deps | `bcrypt` 4.x breaks `passlib` 1.7.4 → register 500s | Pin `bcrypt==4.0.1` |
| 6 | `adapters/sqlalchemy_storage.py` | `_project_to_domain/_to_model/_update` read/write `model.story_dna`, `topic_analysis`, `target_words`, `total_chapters` — **none exist**; real columns are `*_json` (JSON strings) and `chapter_count` | Rewrote all three to (de)serialize the `_json` columns and map `chapter_count` |
| 7 | `adapters/sqlalchemy_storage.py` | `save_phase_result` wrote `output=` but column is `output_json` (JSON string) | Serialize to `output_json` |
| 8 | `adapters/sqlalchemy_storage.py` | Pipeline-run mapping used non-existent `auto_approve` / `estimated_cost_usd` columns | Persist them inside the existing `state_json` blob |
| 9 | `adapters/sqlalchemy_storage.py` | `get_pipeline_run` / `save_phase_result` used `scalar_one_or_none()` without `LIMIT 1` → `MultipleResultsFound` once >1 run exists | `order_by(id.desc()).limit(1)` + `.scalars().first()` |
| 10 | `adapters/websocket_events.py` | Called `manager.broadcast_to_project()` (doesn't exist) and double-JSON-encoded | Call `manager.broadcast()` with the dict |

**Root cause pattern:** the WIP rewrite changed the ORM models (to `_json` string columns)
but never updated the storage adapter or the alembic chain — so the pipeline had never
been executed once. All fixes are in the working tree (uncommitted, alongside the original WIP).

**Migration/model drift still open (not blocking):** Postgres migration 003 also creates
`blueprints` and `project_content` tables that no ORM model maps. Harmless for the current
flow (the adapter uses `phase_results` / `story_bibles`), but worth reconciling.

---

# Storica — Architecture & State Report (original)

> Written 2026-06-29. A point-in-time map of what Storica is, how the agent pipeline
> actually works, what code is real vs. dead, and a prioritized fix list.
> No code was changed to produce this — it is a read-only investigation.

---

## 1. What Storica is

An **AI novel-generation platform**. A user fills out a "Story DNA" quiz, picks an
author **House** (a YAML personality profile — currently Dürrenmatt and Hemingway),
and a pipeline of LLM agents writes a full novel chapter by chapter. Progress streams
to the frontend live over WebSocket, and the pipeline pauses for user approval between
the major planning phases.

| Layer | Technology |
|-------|------------|
| Backend | FastAPI (async), hexagonal architecture (ports/adapters + DI container) |
| Database | PostgreSQL / SQLAlchemy 2.0 (SQLite fallback) |
| LLM | **Anthropic Claude** — Sonnet for planning, **Opus for prose** |
| Real-time | WebSocket event stream |
| Frontend | React 18 + TypeScript + Vite + Tailwind + Zustand + TanStack Query |

---

## 2. Architecture (hexagonal)

The backend is a clean ports-and-adapters design:

- **Domain** (`core/domain/`) — pure entities (`Author`, `Project`, `PipelineRun`,
  `StoryDNA`, `PhaseType`) and value objects (`GenerationConfig`). No framework code.
- **Ports** (`core/ports/`) — interfaces: `LLMPort`, `StoragePort`, `EventPort`,
  `AuthorPort`. The use case depends only on these.
- **Use case** (`core/usecases/generate_story.py`) — `GenerateStoryUseCase`, the
  orchestrator. A thin conductor that walks the phases and delegates to agents.
- **Adapters** (`adapters/`) — concrete implementations:
  `AnthropicLLMAdapter`, `SQLAlchemyStorageAdapter`, `WebSocketEventAdapter`,
  `YAMLAuthorAdapter`.
- **Agents** (`agents/`) — the real workers, one package per phase, self-registering
  into an `AgentRegistry`.
- **Container** (`container.py`) — wires everything together with DI.
- **API** (`api/`) — FastAPI routers: `auth`, `projects`, `authors`, `pipeline`, `websocket`.

**Design principle (from project memory):** keep logic in the **agent layer**, keep the
use case a thin orchestrator. This was the point of the 2026-04 rewrite.

---

## 3. The agentic workflow, end-to-end

### Trigger
`POST /pipeline/projects/{id}/start` (`api/pipeline.py`) kicks off
`GenerateStoryUseCase.execute()` in a FastAPI background task and returns immediately.
The client then watches `WS /ws/projects/{id}` for live events and/or polls
`GET /pipeline/projects/{id}/status`.

### The 8 phases (sequential)

Output of each phase is threaded into the next via a `previous_outputs` dict and an
`AgentContext` that also accumulates token counts.

| # | Phase | Agent | LLM | Notes |
|---|-------|-------|-----|-------|
| 0 | Author loading | *(inline, no agent/LLM)* | — | Loads YAML profile → rich style guide |
| 1 | Topic exploration | `TopicExplorerAgent` | Sonnet | themes, philosophical angles, ironies |
| 2 | Thesis | `ThesisDeveloperAgent` | Sonnet | central thesis + antithesis, moral complexity |
| 3 | Characters | `CharacterDeriverAgent` | Sonnet | protagonist / antagonist / supporting cast |
| 4 | Architecture | `StoryArchitectAgent` | Sonnet | acts, turning points, chapter pacing |
| 5 | Blueprints | `BlueprintPlannerAgent` | Sonnet | per-chapter plan (loops over all chapters) |
| 6 | Prose | **`ProseGenerationLoop`** | Sonnet+**Opus** | multi-agent loop, see below |
| 7 | Consistency | `ConsistencyGuardianAgent` | Sonnet | checks chapter vs. story bible, updates it |

### Phase 6 — the heart (per-chapter multi-agent loop)

```
Reasoner ──> Writer ──> Critic ──(score >= 7.0?)──> done
   ^                       │ no
   └──────  Reviser  <─────┘     (up to PIPELINE_MAX_ITERATIONS = 3)
```

- **ProseReasonerAgent** (Sonnet) — plans voice calibration, opening strategy, key moments
- **ProseWriterAgent** (**Opus**, streaming) — writes the prose, streams chunks to client
- **ProseCriticAgent** (Sonnet) — scores Voice / Blueprint-adherence / Consistency / Quality
- **ProseReviserAgent** (**Opus**) — revises against critique feedback, loops back to Critic

The loop breaks when the critic passes the threshold (`PIPELINE_PASSING_THRESHOLD = 7.0`)
or it hits max iterations. The phase-6 agents are **instantiated directly** by the loop,
not via the registry.

### Cross-cutting mechanisms

- **Story bible** — a persistent JSON document. Initialized at phase 5, updated after each
  chapter by the Consistency Guardian, and passed forward so later chapters stay coherent.
- **Approval gates** — phases 1–5 are gated. With `auto_approve=False`, the use case raises
  `PipelinePausedError`, sets the run to `AWAITING_APPROVAL`, emits an `approval_required`
  event, and stops. Resuming re-enters `execute()` from where it left off.
- **WebSocket events** — `pipeline_started`, `phase_started`, `phase_completed`,
  `critique_result` (per prose iteration), `pipeline_completed`, `error`.
- **Cost tracking** — tokens accumulate per run; config caps at `MAX_COST_PER_PROJECT`
  (default $50, warn at $25).

---

## 4. What's real vs. dead

### ✅ Live / real code (the working path)
`GenerateStoryUseCase` → agents (registry for 1–5,7; direct for 6) → `AnthropicLLMAdapter`
→ `WebSocketEventAdapter`. Plus: container DI, FastAPI routers, YAML author profiles,
the 8 agents and 4 prose sub-agents. This path is coherent and self-consistent.

### ❌ Dead / vestigial code (built, never called by the live path)
| Code | Why it's dead |
|------|---------------|
| `orchestrator/pipeline.py` (`PipelineOrchestrator`) | Alternative orchestration; only referenced by the orphaned Celery tasks |
| `tasks/` (whole Celery system) | `main.py` never imports it; no task is invoked from the API |
| `services/llm.py` (`LLMService`) | Duplicate of `AnthropicLLMAdapter`; unused |
| `agents/phase0_author/loader.py` (`AuthorMindLoaderAgent`) | Registered, but phase 0 is handled inline and bypasses it |
| `orchestrator/gates.py` (`ApprovalGate`) | Sophisticated async gate; replaced by the simpler `PipelinePausedError` |

> These are leftovers from two earlier design directions (a Celery-driven task queue and an
> alternative orchestrator). They aren't harmful, but they're misleading to a reader and
> should eventually be deleted.

---

## 5. State of the migration — known inconsistencies

The repo has been through **two redesigns** (5-chamber/Gemini → 8-phase-agents/Claude) and
the documentation never caught up. Severity is graded for the fix list below.

1. **Docs say Gemini, code uses Claude.** `README.md`, `docker-compose.yml`, and
   `backend/.env.example` all reference `GEMINI_API_KEY` and "5-stage pipeline". The actual
   code, `requirements.txt` (`anthropic>=0.18.0`), root `.env.example`, and `config.py` all
   use Anthropic. **Misleading, not breaking.**

2. **Uncommitted WIP rewrite.** The current working tree has a large uncommitted change
   (~707 insertions / 494 deletions in `generate_story.py`, plus agent wiring in
   `agents/__init__.py`, `container.py`, `entities.py`, `values.py`, `ports/llm.py`). It
   compiles but **has never been executed end-to-end.** This is the single biggest unknown.

3. **`SETUP_REMAINING.md` is STALE.** It claims `story_dna` isn't wired into the project
   API — but it **already is**, just differently than the doc describes. `api/projects.py`
   defines `StoryDNAInput`, stores `story_dna_json` on create (`projects.py:78`), and exposes
   `GET .../story-dna`. **This is not a live blocker. Ignore SETUP_REMAINING.md.**

4. **Likely real bug: sync/async SQLAlchemy mismatch.** `api/projects.py` uses
   *synchronous* SQLAlchemy (`from sqlalchemy.orm import Session`, `db.query(...)`,
   `db.commit()`), while `database.py` and the storage adapter are built on *async*
   (`AsyncSession`). If `get_db` yields an async session, the project endpoints will fail at
   runtime. **Verify this first when running — it's the most likely early crash.**

5. **No tests.** pytest is a dependency but there are zero `test_*.py` files. The entire
   pipeline is unverified.

6. **Migrations never run.** Three migrations exist (`001_initial`, `002_add_cost_fields`,
   `003_pipeline_rewrite`) but have not been applied to any database.

---

## 6. Prioritized fix list

**P0 — blocks running at all**
1. Resolve the **sync/async SQLAlchemy mismatch** in `api/projects.py` (item 5.4). Confirm
   whether `get_db` is sync or async and make the project endpoints match the rest of the app.
2. Apply DB migrations (`alembic upgrade head`) against a real DB and confirm tables create.
3. Set up `.env` with a real `ANTHROPIC_API_KEY` (+ `SECRET_KEY`/`JWT_SECRET_KEY`).

**P1 — needed for a successful first generation**
4. Do **one small end-to-end run** (e.g. 5 chapters, `auto_approve=True`) and fix whatever
   breaks in the WIP `generate_story.py` path. This is the real validation of the rewrite.
5. Commit the WIP rewrite on a branch once it's verified, so the in-flight work is safe.

**P2 — coherence & maintainability**
6. Fix the docs: `README.md`, `docker-compose.yml`, `backend/.env.example` → Claude, 8 phases.
   Delete or correct `SETUP_REMAINING.md` (stale).
7. Delete the dead code (section 4) or move it behind a clearly-labeled `experimental/` path.
8. Add a smoke test: register → create project → start generation (mocked LLM) → assert the
   phases advance and events fire.

**P3 — product**
9. Add more author Houses (the `_template.yaml` exists for this).
10. Decide whether the Celery path is ever coming back; if not, remove `tasks/` entirely.

---

## 7. How to run (reference)

```bash
# 1. Infra
docker-compose up -d postgres redis

# 2. Config
cp .env.example .env        # set ANTHROPIC_API_KEY, SECRET_KEY, JWT_SECRET_KEY,
                            # DATABASE_URL=postgresql+asyncpg://storica:storica@localhost:5433/storica

# 3. Backend
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload         # http://localhost:8000/docs

# 4. Frontend
cd ../frontend
npm install
npm run dev                           # http://localhost:5173
```

> Celery is **not** required — the live pipeline runs in a FastAPI background task, not via
> the Celery worker the README mentions.

---

## 8. One-paragraph summary

Storica is a hexagonal-architecture FastAPI + React app that generates novels via an 8-phase
Claude-agent pipeline, the centerpiece being a per-chapter Reasoner→Writer→Critic→Reviser loop
with a persistent story bible and human approval gates. The primary code path is clean and
coherent, but the repo is mid-migration: documentation still describes the old Gemini/5-stage
design, several abandoned subsystems (Celery, an alternate orchestrator, duplicate LLM service)
remain as dead code, there are no tests, and a large rewrite of the orchestrator sits
uncommitted and unrun. The fastest path to confidence is to fix the probable sync/async DB bug,
run migrations, and do one small end-to-end generation — that single run will surface the real
remaining problems.
