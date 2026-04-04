# Storica Setup - Remaining Steps

Due to iCloud sync issues, some backend files could not be updated directly.
Please apply these changes manually.

## 1. Update Backend Project Schema

Edit `backend/app/schemas/project.py` to import and use StoryDNA:

```python
from typing import Optional, Any
from pydantic import BaseModel, Field
from .story_dna import StoryDNA

class ProjectCreate(BaseModel):
    name: str
    author_id: str
    target_words: int = Field(default=60000, ge=20000, le=150000)
    total_chapters: int = Field(default=12, ge=5, le=50)
    seed: Optional[str] = None
    story_dna: Optional[StoryDNA] = None  # ADD THIS LINE
```

## 2. Update Backend Schemas __init__.py

Edit `backend/app/schemas/__init__.py` to export StoryDNA:

```python
from .story_dna import StoryDNA, ProjectCreateWithDNA
```

## 3. Update Projects API

Edit `backend/app/api/projects.py` to handle story_dna:

In the create_project endpoint, after creating the project, if story_dna is provided:

```python
@router.post("/", response_model=ProjectResponse)
async def create_project(
    project: ProjectCreate,  # This now includes story_dna
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # ... existing code ...

    # If story_dna is provided, convert it to seed text
    if project.story_dna:
        db_project.seed = project.story_dna.to_seed_text()
        db_project.target_words = project.story_dna.structure.target_words
        db_project.total_chapters = project.story_dna.structure.chapter_count

    # ... rest of existing code ...
```

## 4. Database Migration

Run the migration to add cost fields:

```bash
cd backend
alembic upgrade head
```

## 5. Environment Variables

Ensure `.env` has:

```
GEMINI_API_KEY=your_key_here
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=postgresql+asyncpg://storica:storica@localhost:5433/storica
COST_WARNING_EUR=2.5
COST_LIMIT_EUR=3.0
```

## 6. Install Dependencies

```bash
cd backend
pip install pydantic-settings google-generativeai
```

## 7. Start Services

```bash
docker-compose up -d
cd frontend && npm run dev
```

## 8. Verify

1. Create a new project via the Quiz
2. Check the generation endpoints work
3. Monitor WebSocket for live updates
