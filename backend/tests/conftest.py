"""Tests run against a separate database, cinescope_test, created and migrated on first use."""

import asyncio
import os
from datetime import UTC, date, datetime, timedelta

# Must be set before app modules import settings and create the engine.
BASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://cinescope:cinescope@localhost:5433/cinescope"
)
os.environ["JWT_SECRET"] = "test-secret-that-is-at-least-32-bytes-long"
os.environ["DATABASE_URL"] = BASE_URL.rsplit("/", 1)[0] + "/cinescope_test"

import asyncpg  # noqa: E402
import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import insert, text  # noqa: E402

from alembic import command  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Genre, Movie, movie_genres  # noqa: E402


async def _create_test_database() -> None:
    dsn = BASE_URL.replace("postgresql+asyncpg", "postgresql")
    conn = await asyncpg.connect(dsn)
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = 'cinescope_test'")
        if not exists:
            await conn.execute("CREATE DATABASE cinescope_test")
    finally:
        await conn.close()


@pytest.fixture(scope="session", autouse=True)
async def database():
    await _create_test_database()
    # Alembic's env.py calls asyncio.run(), so run it outside this event loop.
    await asyncio.to_thread(command.upgrade, Config("alembic.ini"), "head")


@pytest.fixture(autouse=True)
async def clean_tables(database):
    async with SessionLocal() as session:
        tables = "users, movies, genres, movielens_ratings"
        await session.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
        await session.commit()


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def catalog():
    """Telugu, Hindi and English movies; only the first two are in the catalog."""
    today = date.today()
    synced = datetime.now(UTC)
    movies = [
        {
            "id": 1,
            "title": "Baahubali: The Beginning",
            "original_language": "te",
            "release_date": date(2015, 7, 10),
            "popularity": 50.0,
            "vote_average": 7.5,
            "vote_count": 1500,
            "tmdb_synced_at": synced,
        },
        {
            "id": 2,
            "title": "RRR",
            "original_language": "te",
            "release_date": date(2022, 3, 25),
            "popularity": 90.0,
            "vote_average": 7.8,
            "vote_count": 2000,
            "tmdb_synced_at": synced,
        },
        {
            "id": 3,
            "title": "3 Idiots",
            "original_language": "hi",
            "release_date": date(2009, 12, 25),
            "popularity": 40.0,
            "vote_average": 8.0,
            "vote_count": 3000,
            "tmdb_synced_at": synced,
        },
        {
            "id": 4,
            "title": "Future Telugu Film",
            "original_language": "te",
            "release_date": today + timedelta(days=30),
            "popularity": 10.0,
            "tmdb_synced_at": synced,
        },
        {
            "id": 5,
            "title": "The Matrix",
            "original_language": "en",
            "release_date": date(1999, 3, 31),
            "popularity": 99.0,
            "tmdb_synced_at": synced,
        },
        {"id": 6, "title": "TMDB #123", "original_language": None, "tmdb_synced_at": None},
    ]
    async with SessionLocal() as session:
        await session.execute(
            insert(Genre), [{"id": 28, "name": "Action"}, {"id": 35, "name": "Comedy"}]
        )
        await session.execute(insert(Movie), movies)
        await session.execute(
            insert(movie_genres),
            [
                {"movie_id": 1, "genre_id": 28},
                {"movie_id": 2, "genre_id": 28},
                {"movie_id": 3, "genre_id": 35},
            ],
        )
        await session.commit()
