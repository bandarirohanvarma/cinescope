"""Content-based recommendations with pgvector.

A user's taste vector is the weighted mean of the embeddings of movies they interacted with:
rating 5 -> +2.5, rating 1 -> -1.5 (disliked movies push away), watchlist -> +1.
Candidates are the nearest movies to that vector, then re-ranked with quality and popularity
so the list isn't just obscure look-alikes. New users get popular movies in their favorite
genres (cold start).
"""

import math
import uuid
from dataclasses import dataclass

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DiaryEntry, Movie, Rating, UserPreferences, WatchlistItem, movie_genres

NEUTRAL_RATING = 2.5
WATCHLIST_WEIGHT = 1.0
CANDIDATES = 200
# Final score = similarity + QUALITY * normalized rating + POPULARITY * log-popularity share.
QUALITY_WEIGHT = 0.15
POPULARITY_WEIGHT = 0.10
MIN_VOTES = 5


@dataclass
class Scored:
    movie: Movie
    score: float
    reason: str


def catalog(languages: list[str]):
    return [
        Movie.tmdb_synced_at.is_not(None),
        Movie.embedding.is_not(None),
        Movie.original_language.in_(languages),
    ]


async def user_languages(
    session: AsyncSession, user_id: uuid.UUID, allowed: list[str]
) -> list[str]:
    prefs = await session.get(UserPreferences, user_id)
    chosen = [lang for lang in (prefs.languages if prefs else []) if lang in allowed]
    return chosen or allowed


async def seen_movie_ids(session: AsyncSession, user_id: uuid.UUID) -> set[int]:
    rated = select(Rating.movie_id).where(Rating.user_id == user_id)
    logged = select(DiaryEntry.movie_id).where(DiaryEntry.user_id == user_id)
    listed = select(WatchlistItem.movie_id).where(WatchlistItem.user_id == user_id)
    rows = await session.scalars(rated.union(logged, listed))
    return set(rows)


async def taste_vector(session: AsyncSession, user_id: uuid.UUID) -> np.ndarray | None:
    weights: dict[int, float] = {}
    for movie_id, rating in await session.execute(
        select(Rating.movie_id, Rating.rating).where(Rating.user_id == user_id)
    ):
        weights[movie_id] = float(rating) - NEUTRAL_RATING
    for movie_id in await session.scalars(
        select(WatchlistItem.movie_id).where(WatchlistItem.user_id == user_id)
    ):
        weights.setdefault(movie_id, WATCHLIST_WEIGHT)
    for movie_id in await session.scalars(
        select(DiaryEntry.movie_id).where(
            DiaryEntry.user_id == user_id, DiaryEntry.rating.is_(None)
        )
    ):
        weights.setdefault(movie_id, WATCHLIST_WEIGHT)  # watched, unrated: mild interest
    if not weights:
        return None

    rows = await session.execute(
        select(Movie.id, Movie.embedding).where(Movie.id.in_(weights), Movie.embedding.is_not(None))
    )
    vector = sum((weights[mid] * np.asarray(emb) for mid, emb in rows), np.zeros(384))
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm > 0 else None


def rerank(candidates: list[tuple[Movie, float]], reason: str, limit: int) -> list[Scored]:
    max_pop = max((m.popularity or 0 for m, _ in candidates), default=0) or 1
    scored = []
    for movie, distance in candidates:
        similarity = 1 - distance
        quality = (movie.vote_average or 0) / 10 if (movie.vote_count or 0) >= MIN_VOTES else 0.5
        popularity = math.log1p(movie.popularity or 0) / math.log1p(max_pop)
        score = similarity + QUALITY_WEIGHT * quality + POPULARITY_WEIGHT * popularity
        scored.append(Scored(movie, score, reason))
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored[:limit]


async def nearest(
    session: AsyncSession,
    vector,
    languages: list[str],
    exclude: set[int],
    limit: int = CANDIDATES,
) -> list[tuple[Movie, float]]:
    distance = Movie.embedding.cosine_distance(vector)
    query = select(Movie, distance).where(*catalog(languages)).order_by(distance).limit(limit)
    if exclude:
        query = query.where(Movie.id.not_in(exclude))
    return [(movie, float(d)) for movie, d in await session.execute(query)]


async def for_user(
    session: AsyncSession, user_id: uuid.UUID, allowed: list[str], limit: int = 20
) -> list[Scored]:
    languages = await user_languages(session, user_id, allowed)
    seen = await seen_movie_ids(session, user_id)
    vector = await taste_vector(session, user_id)
    if vector is None:
        return await cold_start(session, user_id, languages, seen, limit)
    candidates = await nearest(session, vector.tolist(), languages, seen)
    return rerank(candidates, "Based on your ratings", limit)


async def cold_start(
    session: AsyncSession, user_id: uuid.UUID, languages: list[str], seen: set[int], limit: int
) -> list[Scored]:
    prefs = await session.get(UserPreferences, user_id)
    query = (
        select(Movie)
        .where(*catalog(languages), Movie.vote_count >= 50)
        .order_by((Movie.vote_average * func.log(Movie.vote_count + 1)).desc())
        .limit(limit)
    )
    if prefs and prefs.favorite_genre_ids:
        in_genres = select(movie_genres.c.movie_id).where(
            movie_genres.c.genre_id.in_(prefs.favorite_genre_ids)
        )
        query = query.where(Movie.id.in_(in_genres))
    if seen:
        query = query.where(Movie.id.not_in(seen))
    return [Scored(m, 0.0, "Popular and highly rated") for m in await session.scalars(query)]


async def similar_to(
    session: AsyncSession, movie: Movie, allowed: list[str], limit: int = 12
) -> list[Scored]:
    if movie.embedding is None:
        return []
    candidates = await nearest(session, movie.embedding, allowed, {movie.id}, limit=60)
    return rerank(candidates, f"Similar to {movie.title}", limit)


async def because_you_watched(
    session: AsyncSession, user_id: uuid.UUID, allowed: list[str], limit: int = 12
) -> tuple[Movie, list[Scored]] | None:
    """Neighbors of the user's most recent highly rated (>= 4) movie."""
    anchor = await session.scalar(
        select(Movie)
        .join(Rating, Rating.movie_id == Movie.id)
        .where(Rating.user_id == user_id, Rating.rating >= 4, Movie.embedding.is_not(None))
        .order_by(Rating.updated_at.desc())
        .limit(1)
    )
    if anchor is None:
        return None
    languages = await user_languages(session, user_id, allowed)
    seen = await seen_movie_ids(session, user_id)
    candidates = await nearest(session, anchor.embedding, languages, seen | {anchor.id}, limit=60)
    return anchor, rerank(candidates, f"Because you liked {anchor.title}", limit)
