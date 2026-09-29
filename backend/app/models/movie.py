from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

# Dimension of the sentence-embedding model used for semantic search (bge-small / MiniLM).
EMBEDDING_DIM = 384

movie_genres = Table(
    "movie_genres",
    Base.metadata,
    Column("movie_id", ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True),
    Column("genre_id", ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True),
)


class Genre(Base):
    __tablename__ = "genres"

    # TMDB genre id, so no autoincrement.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(50), unique=True)


class Movie(TimestampMixin, Base):
    __tablename__ = "movies"
    __table_args__ = (
        # Trigram indexes for fuzzy title search (pg_trgm).
        Index(
            "ix_movies_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
        Index(
            "ix_movies_original_title_trgm",
            "original_title",
            postgresql_using="gin",
            postgresql_ops={"original_title": "gin_trgm_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # External ids. MovieLens links to TMDB and IMDb; TMDB links to Wikidata.
    tmdb_id: Mapped[int | None] = mapped_column(Integer, unique=True, index=True)
    imdb_id: Mapped[str | None] = mapped_column(String(12), unique=True)
    movielens_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    wikidata_id: Mapped[str | None] = mapped_column(String(20))

    title: Mapped[str] = mapped_column(String(500), index=True)
    original_title: Mapped[str | None] = mapped_column(String(500))
    original_language: Mapped[str | None] = mapped_column(String(10), index=True)
    overview: Mapped[str | None] = mapped_column(Text)
    tagline: Mapped[str | None] = mapped_column(String(500))
    release_date: Mapped[date | None] = mapped_column(Date, index=True)
    runtime_minutes: Mapped[int | None] = mapped_column(Integer)
    # TMDB status: Rumored, Planned, In Production, Post Production, Released, Canceled.
    status: Mapped[str | None] = mapped_column(String(30))
    poster_path: Mapped[str | None] = mapped_column(String(200))
    backdrop_path: Mapped[str | None] = mapped_column(String(200))
    popularity: Mapped[float | None] = mapped_column(Float, index=True)
    vote_average: Mapped[float | None] = mapped_column(Float)
    vote_count: Mapped[int | None] = mapped_column(Integer)

    wikipedia_title: Mapped[str | None] = mapped_column(String(500))
    wikipedia_summary: Mapped[str | None] = mapped_column(Text)

    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))

    tmdb_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    wikipedia_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    genres: Mapped[list[Genre]] = relationship(secondary=movie_genres, lazy="selectin")
