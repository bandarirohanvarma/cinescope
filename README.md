# CineScope

A full-stack Telugu and Hindi movie platform: log and rate what you watch, track upcoming releases with reminders,
get personalized recommendations, and ask CineBot anything about movies.

Learning project, non-commercial. Movie data from [TMDB](https://www.themoviedb.org) and
[MovieLens](https://grouplens.org/datasets/movielens/); summaries from Wikipedia (CC BY-SA).
This product uses the TMDB API but is not endorsed or certified by TMDB.

## Stack

| Layer | Tech |
|---|---|
| Frontend | Next.js (App Router), TypeScript, Tailwind CSS |
| Backend | FastAPI, SQLAlchemy 2 (async), Alembic |
| Data | PostgreSQL + pgvector, Redis, Celery (scheduled jobs) |
| ML / AI | Python recommender (content + collaborative), Groq LLMs for CineBot |
| Tooling | Docker Compose, GitHub Actions, pytest, ruff, ESLint |

## Run locally

Prerequisites: Docker Desktop, Python 3.11, Node 24, pnpm.

```bash
# 1. Config
cp .env.example .env

# 2. Database and cache
docker compose up -d

# 3. Backend (http://localhost:8000, docs at /docs)
cd backend
py -3.11 -m venv .venv
.venv/Scripts/pip install -e ".[dev]"      # macOS/Linux: .venv/bin/pip
.venv/Scripts/alembic upgrade head
.venv/Scripts/uvicorn app.main:app --reload

# 4. Load movies (first time, ~30 min): see "Load data" below

# 5. Frontend (http://localhost:3000)
cd frontend
pnpm install
pnpm dev
```

## Load data

Needs `TMDB_API_KEY` in `.env`. From `backend/`:

```bash
.venv/Scripts/python -m app.pipeline bootstrap   # first time: MovieLens + TMDB + Wikipedia
.venv/Scripts/python -m app.pipeline embed       # recommendation vectors
.venv/Scripts/python -m app.pipeline stats       # catalog counts
```

Keep data fresh with the background worker (runs the schedule in PLAN.md):

```bash
.venv/Scripts/celery -A app.worker worker --beat --pool=solo --loglevel=info
```

## Checks

```bash
cd backend && .venv/Scripts/ruff check app tests && .venv/Scripts/pytest
cd frontend && pnpm lint && pnpm build
```

See [PLAN.md](PLAN.md) for the roadmap.
