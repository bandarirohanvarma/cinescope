"""Top-level pipeline jobs: each opens its own session and clients.

Shared by the CLI (python -m app.pipeline) and the Celery worker (app.worker).
"""

from app.pipeline import sync


async def sync_genres() -> dict:
    async with sync.pipeline_session() as session, sync.tmdb_client() as tmdb:
        return {"genres": await sync.sync_genres(session, tmdb)}


async def import_movielens(dataset: str) -> dict:
    async with sync.pipeline_session() as session:
        return await sync.import_movielens(session, dataset)


async def enrich_tmdb(limit: int | None = None) -> dict:
    async with sync.pipeline_session() as session, sync.tmdb_client() as tmdb:
        return {"enriched": await sync.enrich_from_tmdb(session, tmdb, limit)}


async def enrich_wikipedia(limit: int | None = None) -> dict:
    async with sync.pipeline_session() as session, sync.wikipedia_client() as wiki:
        return {"wikipedia": await sync.enrich_from_wikipedia(session, wiki, limit)}


async def refresh_lists() -> dict:
    """Upcoming, now playing, popular, top rated and trending, then fetch their details."""
    async with sync.pipeline_session() as session, sync.tmdb_client() as tmdb:
        listed = await sync.sync_lists(session, tmdb)
        enriched = await sync.enrich_from_tmdb(session, tmdb)
    embedded = await embed_movies()
    return {"listed": listed, "enriched": enriched} | embedded


async def refresh_changes(days: int = 1) -> dict:
    """Re-fetch movies that were edited on TMDB recently."""
    async with sync.pipeline_session() as session, sync.tmdb_client() as tmdb:
        stale = await sync.sync_changes(session, tmdb, days)
        enriched = await sync.enrich_from_tmdb(session, tmdb)
    return {"changed": stale, "enriched": enriched}


async def embed_movies(refresh: bool = False) -> dict:
    """Vectors for recommendations and similar-movie search."""
    from app.core.config import get_settings
    from app.recommend.embeddings import embed_movies as run

    async with sync.pipeline_session() as session:
        return {"embedded": await run(session, get_settings().tmdb_languages, refresh)}


async def send_due_reminders() -> dict:
    """Mark reminders whose time has come as sent (they show up as in-app notifications)."""
    from datetime import UTC, datetime

    from sqlalchemy import update

    from app.models import Reminder
    from app.models.activity import ReminderStatus

    now = datetime.now(UTC)
    async with sync.pipeline_session() as session:
        result = await session.execute(
            update(Reminder)
            .where(Reminder.status == ReminderStatus.PENDING, Reminder.remind_at <= now)
            .values(status=ReminderStatus.SENT, sent_at=now)
        )
        await session.commit()
    return {"sent": result.rowcount}


async def stats() -> dict:
    async with sync.pipeline_session() as session:
        return await sync.catalog_stats(session)


async def bootstrap(dataset: str = "ml-latest-small") -> dict:
    """First-time load: genres, MovieLens, TMDB lists, TMDB details, Wikipedia."""
    await sync_genres()
    await import_movielens(dataset)
    await refresh_lists()
    await enrich_wikipedia()
    await embed_movies(refresh=True)  # re-embed with Wikipedia text
    return await stats()
