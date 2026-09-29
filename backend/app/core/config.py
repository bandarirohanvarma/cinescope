from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    app_name: str = "CineScope API"
    environment: str = "local"

    database_url: str = "postgresql+asyncpg://cinescope:cinescope@localhost:5433/cinescope"
    # Only the Celery worker needs Redis; set REDIS_URL="" where there is no worker.
    redis_url: str = "redis://localhost:6379/0"

    cors_origins: list[str] = ["http://localhost:3000"]

    jwt_secret: str = "change-me-in-production"

    # Data pipeline
    data_dir: Path = REPO_ROOT / "data"
    tmdb_api_key: str | None = None
    # Region used for upcoming / now-playing lists and release dates.
    tmdb_region: str = "IN"
    # Original languages to pull in depth (ISO 639-1): Telugu, Hindi.
    tmdb_languages: list[str] = ["te", "hi"]
    tmdb_concurrency: int = 10
    # Wikimedia asks API clients to identify themselves with a descriptive User-Agent.
    wikimedia_user_agent: str = (
        "CineScope/0.1 (https://github.com/cinescope/cinescope; educational project) httpx"
    )

    # Chatbot (Phase 6)
    groq_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
