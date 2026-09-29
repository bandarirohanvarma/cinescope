"""The signed-in user's ratings, diary, watchlist, reminders and stats."""

from datetime import UTC, datetime, time, timedelta

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from app.api.deps import CurrentUser
from app.db.session import SessionDep
from app.models import (
    DiaryEntry,
    Genre,
    Movie,
    Rating,
    Reminder,
    WatchlistItem,
    movie_genres,
)
from app.models.activity import ReminderStatus
from app.schemas.activity import (
    DiaryIn,
    DiaryOut,
    DiaryUpdate,
    MovieState,
    RatingIn,
    ReminderOut,
    Stats,
    WatchlistOut,
)

router = APIRouter(prefix="/me", tags=["me"])

# Reminders fire at 09:00 India time (03:30 UTC) on release day.
REMINDER_TIME_UTC = time(3, 30, tzinfo=UTC)


async def get_movie_or_404(session: SessionDep, movie_id: int) -> Movie:
    movie = await session.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Movie not found")
    return movie


async def upsert_rating(session: SessionDep, user_id, movie_id: int, rating: float) -> None:
    stmt = insert(Rating).values(user_id=user_id, movie_id=movie_id, rating=rating)
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=["user_id", "movie_id"],
            set_={"rating": stmt.excluded.rating, "updated_at": func.now()},
        )
    )


# --- Ratings ---------------------------------------------------------------


@router.put("/ratings/{movie_id}", status_code=status.HTTP_204_NO_CONTENT)
async def rate_movie(movie_id: int, body: RatingIn, user: CurrentUser, session: SessionDep):
    await get_movie_or_404(session, movie_id)
    await upsert_rating(session, user.id, movie_id, body.rating)
    await session.commit()


@router.delete("/ratings/{movie_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unrate_movie(movie_id: int, user: CurrentUser, session: SessionDep):
    await session.execute(
        delete(Rating).where(Rating.user_id == user.id, Rating.movie_id == movie_id)
    )
    await session.commit()


@router.get("/movies/{movie_id}", response_model=MovieState)
async def movie_state(movie_id: int, user: CurrentUser, session: SessionDep) -> MovieState:
    rating = await session.scalar(
        select(Rating.rating).where(Rating.user_id == user.id, Rating.movie_id == movie_id)
    )
    in_watchlist = await session.get(WatchlistItem, (user.id, movie_id)) is not None
    reminder = await session.scalar(
        select(func.count())
        .select_from(Reminder)
        .where(
            Reminder.user_id == user.id,
            Reminder.movie_id == movie_id,
            Reminder.status == ReminderStatus.PENDING,
        )
    )
    watched = await session.scalar(
        select(func.count())
        .select_from(DiaryEntry)
        .where(DiaryEntry.user_id == user.id, DiaryEntry.movie_id == movie_id)
    )
    return MovieState(
        rating=float(rating) if rating is not None else None,
        in_watchlist=in_watchlist,
        reminder=bool(reminder),
        times_watched=watched or 0,
    )


# --- Diary -----------------------------------------------------------------


async def diary_out(session: SessionDep, entry: DiaryEntry) -> DiaryOut:
    movie = await session.get(Movie, entry.movie_id)
    return DiaryOut.model_validate(
        {**{c: getattr(entry, c) for c in DiaryOut.model_fields if c != "movie"}, "movie": movie}
    )


@router.get("/diary", response_model=list[DiaryOut])
async def list_diary(user: CurrentUser, session: SessionDep) -> list[DiaryOut]:
    entries = await session.scalars(
        select(DiaryEntry)
        .where(DiaryEntry.user_id == user.id)
        .order_by(DiaryEntry.watched_on.desc(), DiaryEntry.id.desc())
    )
    return [await diary_out(session, e) for e in entries]


@router.post("/diary", response_model=DiaryOut, status_code=status.HTTP_201_CREATED)
async def add_diary(body: DiaryIn, user: CurrentUser, session: SessionDep) -> DiaryOut:
    await get_movie_or_404(session, body.movie_id)
    entry = DiaryEntry(user_id=user.id, **body.model_dump())
    session.add(entry)
    if body.rating is not None:
        await upsert_rating(session, user.id, body.movie_id, body.rating)
    # Watching a movie takes it off the watchlist.
    await session.execute(
        delete(WatchlistItem).where(
            WatchlistItem.user_id == user.id, WatchlistItem.movie_id == body.movie_id
        )
    )
    await session.commit()
    return await diary_out(session, entry)


async def own_entry(session: SessionDep, user: CurrentUser, entry_id: int) -> DiaryEntry:
    entry = await session.get(DiaryEntry, entry_id)
    if entry is None or entry.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Diary entry not found")
    return entry


@router.patch("/diary/{entry_id}", response_model=DiaryOut)
async def update_diary(
    entry_id: int, body: DiaryUpdate, user: CurrentUser, session: SessionDep
) -> DiaryOut:
    entry = await own_entry(session, user, entry_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)
    if body.rating is not None:
        await upsert_rating(session, user.id, entry.movie_id, body.rating)
    await session.commit()
    return await diary_out(session, entry)


@router.delete("/diary/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_diary(entry_id: int, user: CurrentUser, session: SessionDep):
    await session.delete(await own_entry(session, user, entry_id))
    await session.commit()


# --- Watchlist -------------------------------------------------------------


@router.get("/watchlist", response_model=list[WatchlistOut])
async def list_watchlist(user: CurrentUser, session: SessionDep) -> list[WatchlistOut]:
    rows = await session.execute(
        select(WatchlistItem.added_at, Movie)
        .join(Movie, Movie.id == WatchlistItem.movie_id)
        .where(WatchlistItem.user_id == user.id)
        .order_by(WatchlistItem.added_at.desc())
    )
    return [WatchlistOut(added_at=added, movie=movie) for added, movie in rows]


@router.put("/watchlist/{movie_id}", status_code=status.HTTP_204_NO_CONTENT)
async def add_watchlist(movie_id: int, user: CurrentUser, session: SessionDep):
    await get_movie_or_404(session, movie_id)
    await session.execute(
        insert(WatchlistItem).values(user_id=user.id, movie_id=movie_id).on_conflict_do_nothing()
    )
    await session.commit()


@router.delete("/watchlist/{movie_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_watchlist(movie_id: int, user: CurrentUser, session: SessionDep):
    await session.execute(
        delete(WatchlistItem).where(
            WatchlistItem.user_id == user.id, WatchlistItem.movie_id == movie_id
        )
    )
    await session.commit()


# --- Reminders and notifications -------------------------------------------


async def reminders_out(session: SessionDep, query) -> list[ReminderOut]:
    rows = await session.execute(query.join(Movie, Movie.id == Reminder.movie_id))
    return [
        ReminderOut(id=r.id, remind_at=r.remind_at, status=r.status, sent_at=r.sent_at, movie=movie)
        for r, movie in rows
    ]


@router.get("/reminders", response_model=list[ReminderOut])
async def list_reminders(user: CurrentUser, session: SessionDep) -> list[ReminderOut]:
    return await reminders_out(
        session,
        select(Reminder, Movie)
        .where(Reminder.user_id == user.id, Reminder.status == ReminderStatus.PENDING)
        .order_by(Reminder.remind_at),
    )


@router.put("/reminders/{movie_id}", status_code=status.HTTP_204_NO_CONTENT)
async def set_reminder(movie_id: int, user: CurrentUser, session: SessionDep):
    movie = await get_movie_or_404(session, movie_id)
    today = datetime.now(UTC).date()
    if movie.release_date is None or movie.release_date < today:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Movie has no upcoming release date")
    remind_at = datetime.combine(movie.release_date, REMINDER_TIME_UTC)
    stmt = insert(Reminder).values(
        user_id=user.id, movie_id=movie_id, remind_at=remind_at, status=ReminderStatus.PENDING
    )
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=["user_id", "movie_id", "channel"],
            set_={"remind_at": remind_at, "status": ReminderStatus.PENDING, "sent_at": None},
        )
    )
    await session.commit()


@router.delete("/reminders/{movie_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_reminder(movie_id: int, user: CurrentUser, session: SessionDep):
    await session.execute(
        delete(Reminder).where(Reminder.user_id == user.id, Reminder.movie_id == movie_id)
    )
    await session.commit()


@router.get("/notifications", response_model=list[ReminderOut])
async def notifications(user: CurrentUser, session: SessionDep) -> list[ReminderOut]:
    """Reminders that fired in the last 30 days: "X releases today"."""
    since = datetime.now(UTC) - timedelta(days=30)
    return await reminders_out(
        session,
        select(Reminder, Movie)
        .where(
            Reminder.user_id == user.id,
            Reminder.status == ReminderStatus.SENT,
            Reminder.sent_at >= since,
        )
        .order_by(Reminder.sent_at.desc()),
    )


# --- Stats -----------------------------------------------------------------


@router.get("/stats", response_model=Stats)
async def stats(user: CurrentUser, session: SessionDep) -> Stats:
    mine = DiaryEntry.user_id == user.id
    entries, movies, minutes = (
        await session.execute(
            select(
                func.count(DiaryEntry.id),
                func.count(func.distinct(DiaryEntry.movie_id)),
                func.coalesce(func.sum(Movie.runtime_minutes), 0),
            )
            .join(Movie, Movie.id == DiaryEntry.movie_id)
            .where(mine)
        )
    ).one()
    average = await session.scalar(select(func.avg(Rating.rating)).where(Rating.user_id == user.id))

    genres = await session.execute(
        select(Genre.name, func.count())
        .select_from(DiaryEntry)
        .join(movie_genres, movie_genres.c.movie_id == DiaryEntry.movie_id)
        .join(Genre, Genre.id == movie_genres.c.genre_id)
        .where(mine)
        .group_by(Genre.name)
        .order_by(func.count().desc())
        .limit(5)
    )
    languages = await session.execute(
        select(Movie.original_language, func.count())
        .join(DiaryEntry, DiaryEntry.movie_id == Movie.id)
        .where(mine)
        .group_by(Movie.original_language)
    )
    month = func.to_char(DiaryEntry.watched_on, "YYYY-MM")
    months = await session.execute(
        select(month, func.count()).where(mine).group_by(month).order_by(month.desc()).limit(12)
    )
    distribution = await session.execute(
        select(Rating.rating, func.count()).where(Rating.user_id == user.id).group_by(Rating.rating)
    )
    return Stats(
        movies_watched=movies,
        diary_entries=entries,
        hours_watched=round(minutes / 60, 1),
        average_rating=round(float(average), 2) if average is not None else None,
        top_genres=[{"name": n, "count": c} for n, c in genres],
        by_language={lang or "unknown": c for lang, c in languages},
        by_month=[{"month": m, "count": c} for m, c in reversed(months.all())],
        rating_distribution={str(float(r)): c for r, c in distribution},
    )
