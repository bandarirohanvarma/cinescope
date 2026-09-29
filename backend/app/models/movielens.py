from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MovieLensRating(Base):
    """Historical ratings from the MovieLens dataset, used to train the recommender.

    Kept apart from app users' ratings: MovieLens users are anonymous integers.
    """

    __tablename__ = "movielens_ratings"

    ml_user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    rating: Mapped[float] = mapped_column(Numeric(2, 1))
    rated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
