from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.movie import MovieSummary


def half_star(value: float | None) -> float | None:
    if value is not None and (value < 0.5 or value > 5 or (value * 2) % 1):
        raise ValueError("rating must be 0.5-5 in half-star steps")
    return value


class RatingIn(BaseModel):
    rating: float

    _check = field_validator("rating")(half_star)


class DiaryIn(BaseModel):
    movie_id: int
    watched_on: date
    rating: float | None = None
    review: str | None = Field(default=None, max_length=5000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    is_rewatch: bool = False

    _check = field_validator("rating")(half_star)


class DiaryUpdate(BaseModel):
    watched_on: date | None = None
    rating: float | None = None
    review: str | None = Field(default=None, max_length=5000)
    tags: list[str] | None = None
    is_rewatch: bool | None = None

    _check = field_validator("rating")(half_star)


class DiaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    watched_on: date
    rating: float | None
    review: str | None
    tags: list[str]
    is_rewatch: bool
    movie: MovieSummary


class WatchlistOut(BaseModel):
    added_at: datetime
    movie: MovieSummary


class ReminderOut(BaseModel):
    id: int
    remind_at: datetime
    status: str
    sent_at: datetime | None
    movie: MovieSummary


class MovieState(BaseModel):
    """The signed-in user's relationship with one movie."""

    rating: float | None
    in_watchlist: bool
    reminder: bool
    times_watched: int


class Stats(BaseModel):
    movies_watched: int
    diary_entries: int
    hours_watched: float
    average_rating: float | None
    top_genres: list[dict]
    by_language: dict[str, int]
    by_month: list[dict]
    rating_distribution: dict[str, int]
