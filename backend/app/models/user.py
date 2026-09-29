import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_values


class UserRole(enum.StrEnum):
    USER = "user"
    ADMIN = "admin"


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    # Null for accounts that only sign in with Google.
    hashed_password: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(100))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False, length=20, values_callable=enum_values),
        default=UserRole.USER,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    preferences: Mapped["UserPreferences"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class UserPreferences(TimestampMixin, Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # ISO 3166-1 country code, used for release dates and streaming availability.
    region: Mapped[str] = mapped_column(String(2), default="IN")
    favorite_genre_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list)
    languages: Mapped[list[str]] = mapped_column(ARRAY(String(10)), default=lambda: ["te", "hi"])
    # TMDB watch-provider ids (Netflix, Prime Video, ...).
    streaming_provider_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list)
    email_reminders: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped[User] = relationship(back_populates="preferences")
