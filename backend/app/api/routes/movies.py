from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import extract, func, select

from app.core.config import get_settings
from app.db.session import SessionDep
from app.models import Genre, Movie, movie_genres
from app.schemas.movie import GenreOut, MovieDetail, MoviePage

router = APIRouter(tags=["movies"])

MIN_VOTES_FOR_RATING_SORT = 20
SORTS = {
    "popularity": Movie.popularity.desc().nulls_last(),
    "release_date": Movie.release_date.desc().nulls_last(),
    "rating": Movie.vote_average.desc().nulls_last(),
    "title": Movie.title.asc(),
}


def catalog_filter(language: str | None) -> list:
    """The catalog is limited to the configured languages (currently Telugu and Hindi)."""
    allowed = get_settings().tmdb_languages
    if language and language not in allowed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"language must be one of {allowed}")
    return [
        Movie.tmdb_synced_at.is_not(None),
        Movie.original_language.in_([language] if language else allowed),
    ]


async def paginate(session: SessionDep, query, order_by: list, page: int, size: int) -> MoviePage:
    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    rows = await session.scalars(
        query.order_by(*order_by, Movie.id).offset((page - 1) * size).limit(size)
    )
    return MoviePage(items=list(rows), total=total or 0, page=page, size=size)


@router.get("/movies", response_model=MoviePage)
async def list_movies(
    session: SessionDep,
    q: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    genre_id: int | None = None,
    language: Annotated[str | None, Query(description="te or hi")] = None,
    year: Annotated[int | None, Query(ge=1900, le=2100)] = None,
    sort: Literal["popularity", "release_date", "rating", "title"] = "popularity",
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 20,
) -> MoviePage:
    query = select(Movie).where(*catalog_filter(language))
    order_by = [SORTS[sort]]
    if q:
        term = q.strip()
        query = query.where(
            Movie.title.ilike(f"%{term}%") | Movie.original_title.ilike(f"%{term}%")
        )
        order_by = [func.similarity(Movie.title, term).desc(), *order_by]
    if genre_id is not None:
        in_genre = select(movie_genres.c.movie_id).where(movie_genres.c.genre_id == genre_id)
        query = query.where(Movie.id.in_(in_genre))
    if year is not None:
        query = query.where(extract("year", Movie.release_date) == year)
    if sort == "rating":
        query = query.where(Movie.vote_count >= MIN_VOTES_FOR_RATING_SORT)
    return await paginate(session, query, order_by, page, size)


@router.get("/movies/upcoming", response_model=MoviePage)
async def upcoming_movies(
    session: SessionDep,
    language: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 20,
) -> MoviePage:
    query = select(Movie).where(*catalog_filter(language), Movie.release_date >= date.today())
    return await paginate(session, query, [Movie.release_date.asc()], page, size)


@router.get("/movies/{movie_id}", response_model=MovieDetail)
async def get_movie(movie_id: int, session: SessionDep) -> Movie:
    movie = await session.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Movie not found")
    return movie


@router.get("/genres", response_model=list[GenreOut])
async def list_genres(session: SessionDep) -> list[Genre]:
    return list(await session.scalars(select(Genre).order_by(Genre.name)))
