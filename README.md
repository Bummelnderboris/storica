# Storica

*Where the unwritten waits.*

An AI-powered novel generation platform. Each author style inhabits its own **House**.

## The Concept

**Storica** is a literary city. Within its walls, great authors maintain their Houses — each with a distinct voice, philosophy, and style. When you begin a project, you choose which House will craft your story.

| House | Author | Style |
|-------|--------|-------|
| Haus Dürrenmatt | Friedrich Dürrenmatt | Tragicomic, philosophically grotesque |
| *More houses coming...* | | |

## Features

- **Multi-user authentication** with JWT tokens
- **Real-time progress updates** via WebSocket
- **5-stage novel generation pipeline**: Essence, Architecture, Blueprints, Prose, Polish
- **Approval workflow** for each generation stage
- **House system** for author styles
- **Cost tracking** for LLM usage

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI (async) |
| Database | PostgreSQL + SQLAlchemy 2.0 |
| Task Queue | Celery + Redis |
| Real-time | WebSockets + Redis PubSub |
| Auth | JWT (access + refresh tokens) |
| Frontend | React 18 + TypeScript + Tailwind CSS |

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Gemini API key

### 1. Clone and configure

```bash
cd storica
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

### 2. Start services

```bash
docker-compose up -d
```

### 3. Run database migrations

```bash
docker-compose exec backend alembic upgrade head
```

### 4. Access the application

- Frontend: http://localhost:3000
- API docs: http://localhost:8000/api/docs

## Development Setup

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start PostgreSQL and Redis (Docker)
docker-compose up -d postgres redis

# Run migrations
alembic upgrade head

# Start FastAPI
uvicorn app.main:app --reload

# Start Celery worker (separate terminal)
celery -A app.tasks.celery_app worker --loglevel=info
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## The Five Chambers

Every story in Storica passes through five chambers:

1. **The Essence Chamber** — Capture the philosophical heart
2. **The Architecture Hall** — Design the narrative structure
3. **The Blueprint Room** — Plan each chapter in detail
4. **The Writing Study** — Generate the prose
5. **The Polish Gallery** — Final consistency review

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new citizen
- `POST /api/auth/login` - Enter the city
- `POST /api/auth/refresh` - Refresh your key
- `GET /api/auth/me` - Your profile

### Projects (Stories)
- `GET /api/projects` - List your stories
- `POST /api/projects` - Begin a new story
- `GET /api/projects/{id}` - View story details
- `PATCH /api/projects/{id}` - Update story
- `DELETE /api/projects/{id}` - Abandon story

### Houses (Authors)
- `GET /api/authors` - Tour all Houses
- `GET /api/authors/{id}` - Visit a House

### Generation
- `POST /api/generation/projects/{id}/generate/essence` - Enter Essence Chamber
- `POST /api/generation/projects/{id}/generate/architecture` - Enter Architecture Hall
- `POST /api/generation/projects/{id}/generate/blueprint/{num}` - Enter Blueprint Room
- `POST /api/generation/projects/{id}/generate/chapter/{num}` - Enter Writing Study

### WebSocket
- `WS /api/ws/{project_id}?token=JWT` - Live updates from the chambers

## Project Structure

```
storica/
├── backend/
│   ├── app/
│   │   ├── main.py              # City gates
│   │   ├── config.py            # City laws
│   │   ├── database.py          # The archives
│   │   ├── api/                 # City services
│   │   ├── models/              # Record keeping
│   │   ├── schemas/             # Forms and documents
│   │   ├── services/            # City workers
│   │   └── tasks/               # The craftsmen
│   ├── alembic/                 # City planning
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/          # Building blocks
│   │   ├── hooks/               # City utilities
│   │   ├── pages/               # Districts
│   │   ├── services/            # Messengers
│   │   └── store/               # Memory palace
│   └── package.json
├── docker-compose.yml
└── authors/                     # The Houses
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| SECRET_KEY | City master key | Required |
| JWT_SECRET_KEY | Citizen key signing | Required |
| GEMINI_API_KEY | Oracle connection | Required |
| DATABASE_URL | Archives location | postgresql+asyncpg://... |
| REDIS_URL | Messenger birds | redis://localhost:6379/0 |

---

*Where the unwritten waits.*
