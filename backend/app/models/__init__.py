"""Import every model here so Alembic autogenerate sees the full schema."""

from app.models.activity import DiaryEntry, Rating, Reminder, WatchlistItem
from app.models.movie import Genre, Movie, movie_genres
from app.models.movielens import MovieLensRating
from app.models.user import User, UserPreferences

__all__ = [
    "DiaryEntry",
    "Genre",
    "Movie",
    "MovieLensRating",
    "Rating",
    "Reminder",
    "User",
    "UserPreferences",
    "WatchlistItem",
    "movie_genres",
]
