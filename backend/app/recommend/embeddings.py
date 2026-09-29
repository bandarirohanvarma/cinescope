"""Sentence embeddings for movies (BAAI/bge-small-en-v1.5, 384 dims, runs on CPU via ONNX)."""

import logging
from functools import lru_cache

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models import Movie

logger = logging.getLogger(__name__)

MODEL_NAME = "BAAI/bge-small-en-v1.5"
BATCH = 256


@lru_cache
def model():
    from fastembed import TextEmbedding  # heavy import; only load when needed

    return TextEmbedding(MODEL_NAME, cache_dir=str(get_settings().data_dir / "models"))


def movie_text(movie: Movie) -> str:
    """What a movie is 'about', for embedding."""
    parts = [
        movie.title,
        f"Language: {movie.original_language}" if movie.original_language else "",
        "Genres: " + ", ".join(g.name for g in movie.genres) if movie.genres else "",
        movie.tagline or "",
        movie.overview or "",
        (movie.wikipedia_summary or "")[:1000],
    ]
    return ". ".join(p for p in parts if p)


def embed(texts: list[str]) -> list[list[float]]:
    return [vector.tolist() for vector in model().embed(texts, batch_size=64)]


async def embed_movies(session: AsyncSession, languages: list[str], refresh: bool = False) -> int:
    """Embed enriched movies in the given languages that don't have a vector yet."""
    query = (
        select(Movie)
        .options(selectinload(Movie.genres))
        .where(Movie.tmdb_synced_at.is_not(None), Movie.original_language.in_(languages))
        .order_by(Movie.id)
    )
    if not refresh:
        query = query.where(Movie.embedding.is_(None))
    movies = list(await session.scalars(query))
    logger.info("Embedding %s movies", len(movies))
    for start in range(0, len(movies), BATCH):
        chunk = movies[start : start + BATCH]
        vectors = embed([movie_text(m) for m in chunk])
        for movie, vector in zip(chunk, vectors, strict=True):
            await session.execute(
                update(Movie).where(Movie.id == movie.id).values(embedding=vector)
            )
        await session.commit()
        logger.info("Embedded %s / %s", start + len(chunk), len(movies))
    return len(movies)
