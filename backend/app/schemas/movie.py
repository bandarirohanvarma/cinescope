from datetime import date

from pydantic import BaseModel, ConfigDict, computed_field

IMAGE_BASE = "https://image.tmdb.org/t/p"


class GenreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class MovieSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    original_title: str | None
    original_language: str | None
    release_date: date | None
    vote_average: float | None
    poster_path: str | None
    genres: list[GenreOut]

    @computed_field
    @property
    def poster_url(self) -> str | None:
        return f"{IMAGE_BASE}/w500{self.poster_path}" if self.poster_path else None


class MovieDetail(MovieSummary):
    tmdb_id: int | None
    imdb_id: str | None
    overview: str | None
    tagline: str | None
    runtime_minutes: int | None
    status: str | None
    backdrop_path: str | None
    popularity: float | None
    vote_count: int | None
    wikipedia_title: str | None
    wikipedia_summary: str | None

    @computed_field
    @property
    def backdrop_url(self) -> str | None:
        return f"{IMAGE_BASE}/original{self.backdrop_path}" if self.backdrop_path else None

    @computed_field
    @property
    def wikipedia_url(self) -> str | None:
        if not self.wikipedia_title:
            return None
        return "https://en.wikipedia.org/wiki/" + self.wikipedia_title.replace(" ", "_")


class MoviePage(BaseModel):
    items: list[MovieSummary]
    total: int
    page: int
    size: int
