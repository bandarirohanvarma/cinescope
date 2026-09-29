"""Data pipeline jobs. Each job is idempotent and safe to re-run.

Flow: MovieLens and TMDB lists add movies (possibly as stubs) -> TMDB enrichment fills
details for every movie whose tmdb_synced_at is NULL -> Wikipedia enrichment adds summaries.
Marking a movie stale is just setting tmdb_synced_at back to NULL.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.models import Genre, Movie, MovieLensRating, movie_genres
from app.pipeline import movielens
from app.pipeline.tmdb import TMDBClient, movie_fields
from app.pipeline.wikipedia import WikipediaClient, WikipediaUnavailable

logger = logging.getLogger(__name__)

# How many pages (20 movies each) to pull from each TMDB list.
LIST_PAGES = {"upcoming": 10, "now_playing": 10, "popular": 25, "top_rated": 25}
TRENDING_PAGES = 5
# Per preferred language: popular back catalog and upcoming releases.
LANGUAGE_POPULAR_PAGES = 100
LANGUAGE_UPCOMING_PAGES = 10
ENRICH_CHUNK = 200


@asynccontextmanager
async def pipeline_session() -> AsyncIterator[AsyncSession]:
    """A session on a throwaway engine, so jobs can run under asyncio.run() in any process."""
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            yield session
    finally:
        await engine.dispose()


def tmdb_client() -> TMDBClient:
    settings = get_settings()
    if not settings.tmdb_api_key:
        raise RuntimeError("TMDB_API_KEY is not set in .env")
    return TMDBClient(settings.tmdb_api_key, settings.tmdb_concurrency)


def wikipedia_client() -> WikipediaClient:
    return WikipediaClient(get_settings().wikimedia_user_agent)


async def sync_genres(session: AsyncSession, tmdb: TMDBClient) -> int:
    genres = await tmdb.genres()
    if genres:
        stmt = insert(Genre).values([{"id": g["id"], "name": g["name"]} for g in genres])
        await session.execute(
            stmt.on_conflict_do_update(index_elements=["id"], set_={"name": stmt.excluded.name})
        )
        await session.commit()
    return len(genres)


async def import_movielens(session: AsyncSession, dataset: str) -> dict[str, int]:
    folder = await asyncio.to_thread(movielens.download, dataset, get_settings().data_dir)
    return await movielens.import_dataset(session, folder)


async def mark_stale(session: AsyncSession, tmdb_ids: list[int]) -> None:
    """Add unknown movies as stubs and flag all of them for a TMDB refresh."""
    if not tmdb_ids:
        return
    for start in range(0, len(tmdb_ids), 5_000):
        chunk = tmdb_ids[start : start + 5_000]
        stubs = [{"tmdb_id": tmdb_id, "title": f"TMDB #{tmdb_id}"} for tmdb_id in chunk]
        await session.execute(
            insert(Movie).values(stubs).on_conflict_do_nothing(index_elements=["tmdb_id"])
        )
        await session.execute(
            update(Movie).where(Movie.tmdb_id.in_(chunk)).values(tmdb_synced_at=None)
        )
    await session.commit()


async def sync_lists(session: AsyncSession, tmdb: TMDBClient) -> int:
    """Pull upcoming, now playing, popular, top rated and trending movies from TMDB."""
    settings = get_settings()
    region = settings.tmdb_region
    results = await asyncio.gather(
        *(
            tmdb.movie_list(name, pages, region if name in ("upcoming", "now_playing") else None)
            for name, pages in LIST_PAGES.items()
        ),
        tmdb.trending(TRENDING_PAGES),
        *(
            tmdb.discover(
                LANGUAGE_POPULAR_PAGES, with_original_language=lang, sort_by="popularity.desc"
            )
            for lang in settings.tmdb_languages
        ),
        *(
            tmdb.discover(
                LANGUAGE_UPCOMING_PAGES,
                with_original_language=lang,
                sort_by="primary_release_date.asc",
                **{"primary_release_date.gte": date.today().isoformat()},
            )
            for lang in settings.tmdb_languages
        ),
    )
    tmdb_ids = list(dict.fromkeys(tmdb_id for ids in results for tmdb_id in ids))
    await mark_stale(session, tmdb_ids)
    return len(tmdb_ids)


async def sync_changes(session: AsyncSession, tmdb: TMDBClient, days: int = 1) -> int:
    """Flag movies we store that were edited on TMDB in the last `days` days (max 14)."""
    end = date.today()
    changed = await tmdb.changed_movie_ids(end - timedelta(days=min(days, 14)), end)
    stale = 0
    for start in range(0, len(changed), 5_000):
        result = await session.execute(
            update(Movie)
            .where(Movie.tmdb_id.in_(changed[start : start + 5_000]))
            .values(tmdb_synced_at=None)
        )
        stale += result.rowcount
    await session.commit()
    return stale


async def enrich_from_tmdb(
    session: AsyncSession, tmdb: TMDBClient, limit: int | None = None
) -> int:
    """Fetch TMDB details for every movie that needs them."""
    query = (
        select(Movie.id, Movie.tmdb_id)
        .where(Movie.tmdb_id.is_not(None), Movie.tmdb_synced_at.is_(None))
        .order_by(Movie.id)
    )
    if limit:
        query = query.limit(limit)
    pending = (await session.execute(query)).tuples().all()
    logger.info("TMDB enrichment: %s movies pending", len(pending))

    known_genres = set((await session.execute(select(Genre.id))).scalars())
    done = 0
    for start in range(0, len(pending), ENRICH_CHUNK):
        chunk = pending[start : start + ENRICH_CHUNK]
        details = await asyncio.gather(*(tmdb.movie_details(tmdb_id) for _, tmdb_id in chunk))
        now = datetime.now(UTC)
        for (movie_id, _), payload in zip(chunk, details, strict=True):
            await _apply_details(session, movie_id, payload, now, known_genres)
        await session.commit()
        done += len(chunk)
        logger.info("TMDB enrichment: %s / %s", done, len(pending))
    return done


async def _apply_details(
    session: AsyncSession, movie_id: int, payload: dict | None, now: datetime, known: set[int]
) -> None:
    if payload is None:  # removed from TMDB; don't retry forever
        await session.execute(update(Movie).where(Movie.id == movie_id).values(tmdb_synced_at=now))
        return

    fields = movie_fields(payload) | {"tmdb_synced_at": now}
    try:
        async with session.begin_nested():
            await session.execute(update(Movie).where(Movie.id == movie_id).values(**fields))
    except IntegrityError:
        # Another row already has this IMDb id (duplicate entry upstream): keep ours without it.
        fields["imdb_id"] = None
        await session.execute(update(Movie).where(Movie.id == movie_id).values(**fields))

    # TMDB occasionally repeats a genre in one payload.
    genres = list({g["id"]: g for g in payload.get("genres") or []}.values())
    new_genres = [g for g in genres if g["id"] not in known]
    if new_genres:
        await session.execute(
            insert(Genre)
            .values([{"id": g["id"], "name": g["name"]} for g in new_genres])
            .on_conflict_do_nothing()
        )
        known.update(g["id"] for g in new_genres)
    await session.execute(delete(movie_genres).where(movie_genres.c.movie_id == movie_id))
    if genres:
        await session.execute(
            insert(movie_genres).values(
                [{"movie_id": movie_id, "genre_id": g["id"]} for g in genres]
            )
        )


async def enrich_from_wikipedia(
    session: AsyncSession, wiki: WikipediaClient, limit: int | None = None
) -> int:
    """Attach English Wikipedia summaries to movies that have a Wikidata id."""
    query = (
        select(Movie.id, Movie.wikidata_id)
        .where(
            Movie.wikidata_id.is_not(None),
            Movie.wikipedia_synced_at.is_(None),
            Movie.original_language.in_(get_settings().tmdb_languages),
        )
        .order_by(Movie.popularity.desc().nulls_last())
    )
    if limit:
        query = query.limit(limit)
    pending = (await session.execute(query)).tuples().all()
    logger.info("Wikipedia enrichment: %s movies pending", len(pending))

    done = 0
    for start in range(0, len(pending), 500):
        chunk = pending[start : start + 500]
        try:
            titles = await wiki.enwiki_titles([qid for _, qid in chunk])
        except WikipediaUnavailable:
            logger.warning("Wikidata is throttling us; stopping. Re-run later to continue.")
            break
        summaries = await asyncio.gather(
            *(wiki.summary(titles[qid]) if qid in titles else _none() for _, qid in chunk),
            return_exceptions=True,
        )
        now = datetime.now(UTC)
        for (movie_id, qid), summary in zip(chunk, summaries, strict=True):
            if isinstance(summary, Exception):
                continue  # not marked as synced, so it's retried next run
            await session.execute(
                update(Movie)
                .where(Movie.id == movie_id)
                .values(
                    wikipedia_title=titles.get(qid),
                    wikipedia_summary=summary,
                    wikipedia_synced_at=now,
                )
            )
        await session.commit()
        done += len(chunk)
        logger.info("Wikipedia enrichment: %s / %s", done, len(pending))
    return done


async def _none() -> None:
    return None


async def catalog_stats(session: AsyncSession) -> dict[str, int]:
    def count(*where):
        return select(func.count()).select_from(Movie).where(*where)

    queries = {
        "movies": count(),
        "with_tmdb_details": count(Movie.tmdb_synced_at.is_not(None)),
        "with_wikipedia": count(Movie.wikipedia_summary.is_not(None)),
        "upcoming": count(Movie.release_date > date.today()),
    }
    stats = {name: (await session.execute(q)).scalar_one() for name, q in queries.items()}
    stats["movielens_ratings"] = (
        await session.execute(select(func.count()).select_from(MovieLensRating))
    ).scalar_one()
    return stats
