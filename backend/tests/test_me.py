from datetime import date, timedelta

from sqlalchemy import update

from app.db.session import SessionLocal
from app.models import Movie
from app.pipeline import jobs


async def auth(client, email="asha@example.com"):
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "long-password", "display_name": "Asha"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_diary_entry_sets_rating_and_leaves_watchlist(client, catalog):
    headers = await auth(client)
    await client.put("/api/v1/me/watchlist/2", headers=headers)

    response = await client.post(
        "/api/v1/me/diary",
        json={"movie_id": 2, "watched_on": "2026-09-01", "rating": 4.5, "review": "Mass!"},
        headers=headers,
    )
    state = (await client.get("/api/v1/me/movies/2", headers=headers)).json()

    assert response.status_code == 201
    assert response.json()["movie"]["title"] == "RRR"
    assert state == {"rating": 4.5, "in_watchlist": False, "reminder": False, "times_watched": 1}


async def test_rating_must_be_half_stars(client, catalog):
    headers = await auth(client)
    bad = await client.put("/api/v1/me/ratings/1", json={"rating": 4.3}, headers=headers)
    good = await client.put("/api/v1/me/ratings/1", json={"rating": 3.5}, headers=headers)
    assert (bad.status_code, good.status_code) == (422, 204)


async def test_diary_entries_are_private(client, catalog):
    owner = await auth(client)
    other = await auth(client, "other@example.com")
    entry = await client.post(
        "/api/v1/me/diary", json={"movie_id": 1, "watched_on": "2026-09-01"}, headers=owner
    )
    entry_id = entry.json()["id"]

    assert (await client.delete(f"/api/v1/me/diary/{entry_id}", headers=other)).status_code == 404
    assert (await client.get("/api/v1/me/diary", headers=other)).json() == []


async def test_reminder_only_for_upcoming_and_fires_on_release_day(client, catalog):
    headers = await auth(client)

    past = await client.put("/api/v1/me/reminders/1", headers=headers)
    upcoming = await client.put("/api/v1/me/reminders/4", headers=headers)
    assert (past.status_code, upcoming.status_code) == (400, 204)
    assert len((await client.get("/api/v1/me/reminders", headers=headers)).json()) == 1

    # Release day arrives.
    async with SessionLocal() as session:
        await session.execute(
            update(Movie).where(Movie.id == 4).values(release_date=date.today() - timedelta(days=1))
        )
        await session.commit()
    await client.put("/api/v1/me/reminders/4", headers=headers)  # re-set to the new date fails
    async with SessionLocal() as session:
        from app.models import Reminder

        await session.execute(update(Reminder).values(remind_at=date.today() - timedelta(days=1)))
        await session.commit()
    assert (await jobs.send_due_reminders())["sent"] == 1

    notes = (await client.get("/api/v1/me/notifications", headers=headers)).json()
    assert [n["movie"]["title"] for n in notes] == ["Future Telugu Film"]


async def test_stats(client, catalog):
    headers = await auth(client)
    for movie_id, rating in [(1, 4.0), (2, 5.0), (3, 3.0)]:
        await client.post(
            "/api/v1/me/diary",
            json={"movie_id": movie_id, "watched_on": "2026-09-01", "rating": rating},
            headers=headers,
        )

    stats = (await client.get("/api/v1/me/stats", headers=headers)).json()

    assert stats["movies_watched"] == 3
    assert stats["average_rating"] == 4.0
    assert stats["by_language"] == {"te": 2, "hi": 1}
    assert stats["top_genres"][0] == {"name": "Action", "count": 2}
