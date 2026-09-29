# CineScope roadmap

## Phases

- [x] **0. Foundation**: monorepo, Docker Compose (Postgres + pgvector, Redis), FastAPI skeleton,
      database schema and migrations, Next.js app, CI
- [x] **1. Data pipeline**: MovieLens import (`links.csv` joins to TMDB), TMDB sync jobs
      (`/movie/changes`, `/movie/upcoming`, `/movie/now_playing`), Wikipedia enrichment
      (TMDB → Wikidata → Wikipedia `/page/summary`), Celery worker + scheduler
- [x] **2. Auth and catalog API**: email/password, JWT access + refresh, preferences; movie search
      (pg_trgm), filters, upcoming, detail. Catalog limited to Telugu + Hindi (`TMDB_LANGUAGES`).
      Google login deferred.
- [x] **3. UI**: home rows, browse/search, movie detail (rate, log, watchlist, remind), diary,
      watchlist, upcoming, notifications, stats, CineBot chat; Tailwind, dark theme
- [x] **4. Upcoming and reminders**: release calendar, "Remind me", in-app notifications
      (Celery marks due reminders every 15 min). Email delivery: TODO (needs SMTP/Resend key)
- [x] **5. Recommendations**: bge-small embeddings (fastembed) in pgvector; taste vector from
      ratings/watchlist, re-ranked by quality + popularity; cold start by genres; similar movies.
      Later: collaborative filtering once there are many users (MovieLens has few Telugu/Hindi)
- [x] **6. CineBot**: Groq `openai/gpt-oss-120b` with tools (catalog search, details, upcoming,
      your history, recommendations) and web search via `gpt-oss-20b` browser_search.
      Later: streaming replies, per-user rate limits
- [x] **7. Production (partial)**: stats dashboard, backend Dockerfile, CI. Later: admin panel,
      Sentry, OpenTelemetry, Google login, httpOnly-cookie auth

## Database schema

| Table | Purpose |
|---|---|
| `users`, `user_preferences` | Account, role, region, favorite genres, streaming services |
| `movies`, `genres`, `movie_genres` | Catalog with TMDB / IMDb / MovieLens / Wikidata ids, Wikipedia summary, 384-d embedding |
| `ratings` | One current rating per user and movie (feeds the recommender) |
| `diary_entries` | Each viewing: date, rating, review, tags, rewatch flag |
| `watchlist_items` | Movies to watch |
| `reminders` | Release-day notifications (email / in-app) |
| `movielens_ratings` | MovieLens training ratings (anonymous users), for the recommender |

## Data pipeline

| Job | Schedule | What it does |
|---|---|---|
| `tmdb-lists` | every 6 h | Upcoming, now playing, popular, top rated, trending → add/refresh movies |
| `tmdb-changes` | daily 03:30 UTC | Re-fetch stored movies edited on TMDB |
| `wikipedia` | daily 04:00 UTC | TMDB → Wikidata → English Wikipedia summary |
| `movielens` | manual | Movies + ratings; `--dataset ml-32m` for the full 32M ratings |

## Deployment (free tiers)

1. **Postgres**: Neon (supports `vector` and `pg_trgm`). Copy the connection string into
   `DATABASE_URL` as `postgresql+asyncpg://...`.
2. **Redis**: Upstash → `REDIS_URL`.
3. **API**: Render web service from `backend/Dockerfile` (runs migrations on start). Env vars:
   `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `TMDB_API_KEY`, `GROQ_API_KEY`,
   `CORS_ORIGINS=["https://<your-app>.vercel.app"]`.
4. **Worker**: Render background worker, same image, command
   `celery -A app.worker worker --beat --loglevel=info`.
5. **Frontend**: Vercel, root `frontend/`, env `NEXT_PUBLIC_API_URL=https://<api>.onrender.com`.
6. Load data once: `python -m app.pipeline bootstrap` against the production `DATABASE_URL`.
