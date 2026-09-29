from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.deps import CurrentUser
from app.core.config import get_settings
from app.db.session import SessionDep
from app.models import Movie
from app.recommend import engine
from app.schemas.movie import MovieSummary

router = APIRouter(tags=["recommendations"])


class Recommendation(BaseModel):
    movie: MovieSummary
    score: float
    reason: str


class Row(BaseModel):
    title: str
    items: list[Recommendation]


def out(scored: list[engine.Scored]) -> list[Recommendation]:
    return [Recommendation(movie=s.movie, score=round(s.score, 4), reason=s.reason) for s in scored]


@router.get("/recommendations", response_model=list[Row])
async def recommendations(user: CurrentUser, session: SessionDep) -> list[Row]:
    """Home-feed rows for the signed-in user."""
    allowed = get_settings().tmdb_languages
    rows = [Row(title="For you", items=out(await engine.for_user(session, user.id, allowed)))]
    because = await engine.because_you_watched(session, user.id, allowed)
    if because:
        anchor, items = because
        # With few ratings both rows can match; only show the second when it adds something.
        first_ids = {r.movie.id for r in rows[0].items}
        if {s.movie.id for s in items} - first_ids:
            rows.append(Row(title=f"Because you liked {anchor.title}", items=out(items)))
    return rows


@router.get("/movies/{movie_id}/similar", response_model=list[Recommendation])
async def similar(movie_id: int, session: SessionDep) -> list[Recommendation]:
    movie = await session.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Movie not found")
    return out(await engine.similar_to(session, movie, get_settings().tmdb_languages))
