"""What users do with movies: ratings, diary entries, watchlist and reminders."""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, enum_values

RATING_CHECK = "rating >= 0.5 AND rating <= 5 AND rating * 2 = floor(rating * 2)"


class Rating(TimestampMixin, Base):
    """A user's current rating of a movie (one per user and movie). Feeds the recommender."""

    __tablename__ = "ratings"
    __table_args__ = (
        UniqueConstraint("user_id", "movie_id"),
        CheckConstraint(RATING_CHECK, name="half_star_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"), index=True)
    rating: Mapped[float] = mapped_column(Numeric(2, 1))


class DiaryEntry(TimestampMixin, Base):
    """One viewing of a movie. A user can log the same movie many times (rewatches)."""

    __tablename__ = "diary_entries"
    __table_args__ = (
        CheckConstraint(f"rating IS NULL OR ({RATING_CHECK})", name="half_star_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"), index=True)
    watched_on: Mapped[date] = mapped_column(Date, index=True)
    rating: Mapped[float | None] = mapped_column(Numeric(2, 1))
    review: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(50)), default=list)
    is_rewatch: Mapped[bool] = mapped_column(Boolean, default=False)


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True
    )
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReminderChannel(enum.StrEnum):
    EMAIL = "email"
    IN_APP = "in_app"


class ReminderStatus(enum.StrEnum):
    PENDING = "pending"
    SENT = "sent"
    CANCELLED = "cancelled"


class Reminder(TimestampMixin, Base):
    """Notify a user when an upcoming movie is released."""

    __tablename__ = "reminders"
    __table_args__ = (UniqueConstraint("user_id", "movie_id", "channel"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"))
    remind_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    channel: Mapped[ReminderChannel] = mapped_column(
        Enum(ReminderChannel, native_enum=False, length=20, values_callable=enum_values),
        default=ReminderChannel.EMAIL,
    )
    status: Mapped[ReminderStatus] = mapped_column(
        Enum(ReminderStatus, native_enum=False, length=20, values_callable=enum_values),
        default=ReminderStatus.PENDING,
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
