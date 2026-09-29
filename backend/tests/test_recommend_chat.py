import json
from types import SimpleNamespace

import numpy as np
from sqlalchemy import update

from app.chat.bot import CineBot
from app.db.session import SessionLocal
from app.models import Movie
from tests.test_me import auth


def unit(*values):
    vector = np.zeros(384)
    vector[: len(values)] = values
    return (vector / np.linalg.norm(vector)).tolist()


async def give_embeddings():
    # 1 and 2 (Telugu action) point the same way; 3 (Hindi comedy) elsewhere.
    vectors = {1: unit(1, 0.1), 2: unit(1, 0.2), 3: unit(0, 1), 4: unit(0.9, 0.3)}
    async with SessionLocal() as session:
        for movie_id, vector in vectors.items():
            await session.execute(
                update(Movie).where(Movie.id == movie_id).values(embedding=vector)
            )
        await session.commit()


async def test_recommendations_follow_ratings_and_skip_seen(client, catalog):
    await give_embeddings()
    headers = await auth(client)
    await client.put("/api/v1/me/ratings/1", json={"rating": 5}, headers=headers)

    rows = (await client.get("/api/v1/recommendations", headers=headers)).json()
    for_you = [item["movie"]["id"] for item in rows[0]["items"]]

    assert 1 not in for_you  # already rated
    assert for_you[0] == 2  # closest to what they loved
    assert len(rows) == 1  # "Because you liked" would repeat "For you" with one rating


async def test_similar_movies_stay_in_catalog_languages(client, catalog):
    await give_embeddings()
    similar = (await client.get("/api/v1/movies/1/similar")).json()
    ids = [s["movie"]["id"] for s in similar]
    assert ids[0] == 2
    assert 5 not in ids  # English movie excluded


class FakeGroq:
    """Scripted chat completions: first a tool call, then a final answer."""

    def __init__(self, replies):
        self.replies = iter(replies)
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=next(self.replies))])


def tool_call(name, arguments):
    call = SimpleNamespace(
        id="call_1", function=SimpleNamespace(name=name, arguments=json.dumps(arguments))
    )
    call.model_dump = lambda: {
        "id": "call_1",
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }
    return SimpleNamespace(content="", tool_calls=[call])


async def test_cinebot_uses_catalog_tool_then_answers(catalog):
    fake = FakeGroq(
        [
            tool_call("search_movies", {"title": "RRR"}),
            SimpleNamespace(content="RRR (2022) is a Telugu epic.", tool_calls=None),
        ]
    )
    async with SessionLocal() as session:
        import uuid

        bot = CineBot(session, uuid.uuid4(), client=fake)
        result = await bot.reply([{"role": "user", "content": "Tell me about RRR"}], "Asha")

    assert result == {"answer": "RRR (2022) is a Telugu epic.", "tools_used": ["search_movies"]}
    tool_message = fake.requests[1]["messages"][-1]
    assert tool_message["role"] == "tool"
    assert json.loads(tool_message["content"])[0]["title"] == "RRR"
