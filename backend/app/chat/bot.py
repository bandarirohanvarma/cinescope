"""CineBot: a Groq-hosted LLM with tools over the catalog, the user's history and the web."""

import json
import logging
import re
import uuid
from datetime import date
from typing import Any

from groq import AsyncGroq
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import DiaryEntry, Genre, Movie, Rating, WatchlistItem, movie_genres
from app.recommend import engine

logger = logging.getLogger(__name__)

CHAT_MODEL = "openai/gpt-oss-120b"
# Groq's built-in browser search is available on the gpt-oss models.
SEARCH_MODEL = "openai/gpt-oss-20b"
MAX_TOOL_ROUNDS = 6
CITATION_MARK = re.compile(r"【[^】]*】")

SYSTEM_PROMPT = """You are CineBot, the movie expert inside CineScope, an app focused on \
Telugu and Hindi cinema. Today is {today}. The user's name is {name}.

You can answer ANY question about movies, actors, directors, music, box office, OTT releases, \
reviews, trivia or film news, in any language or industry.

How to find answers:
1. For movies in the CineScope catalog, start with search_movies, get_movie or upcoming_movies.
2. For anything about the user's own watching, use my_history; for suggestions, use recommend.
3. Use web_search whenever the tools above return nothing, lack the detail asked for (cast, \
crew, songs, budget, box office, OTT platform, reviews, awards, news), or the question is about \
something outside the catalog. Never say you don't know before trying web_search.
4. Never invent facts. If even web_search can't confirm something, say so.

How to write answers (Markdown):
- Start with a direct one-line answer, then details.
- Use **bold** for movie titles, followed by the year in parentheses, e.g. **RRR** (2022).
- Use bullet lists for several items and a table when comparing movies (title, year, rating).
- Use short `###` headings only for longer answers with distinct parts.
- Keep it concise: usually under 200 words.
- If you used web_search, end with a "Sources" line listing the source links you were given."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_movies",
            "description": "Search the CineScope catalog (Telugu and Hindi movies).",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Part of the title"},
                    "language": {"type": "string", "enum": ["te", "hi"]},
                    "genre": {"type": "string", "description": "e.g. Action, Comedy, Drama"},
                    "year": {"type": "integer"},
                    "sort": {"type": "string", "enum": ["popularity", "rating", "newest"]},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_movie",
            "description": "Full details of one movie, including its Wikipedia summary.",
            "parameters": {
                "type": "object",
                "properties": {"movie_id": {"type": "integer"}},
                "required": ["movie_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "upcoming_movies",
            "description": "Movies releasing from today onward, soonest first.",
            "parameters": {
                "type": "object",
                "properties": {"language": {"type": "string", "enum": ["te", "hi"]}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "my_history",
            "description": "The user's diary (watched movies), ratings and watchlist.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recommend",
            "description": "Personalized movie recommendations for the user.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the web for any movie information the database lacks: cast, crew, "
                "music, box office, OTT platform, reviews, awards, news, non-catalog movies."
            ),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
]


def brief(movie: Movie) -> dict[str, Any]:
    return {
        "id": movie.id,
        "title": movie.title,
        "language": movie.original_language,
        "release_date": movie.release_date.isoformat() if movie.release_date else None,
        "rating": movie.vote_average,
        "genres": [g.name for g in movie.genres],
    }


class CineBot:
    def __init__(self, session: AsyncSession, user_id: uuid.UUID, client: AsyncGroq | None = None):
        settings = get_settings()
        self.session = session
        self.user_id = user_id
        self.languages = settings.tmdb_languages
        self.client = client or AsyncGroq(api_key=settings.groq_api_key)

    async def reply(self, messages: list[dict[str, str]], user_name: str) -> dict[str, Any]:
        system = SYSTEM_PROMPT.format(today=date.today().isoformat(), name=user_name)
        conversation: list[dict[str, Any]] = [{"role": "system", "content": system}, *messages]
        used: list[str] = []

        for _ in range(MAX_TOOL_ROUNDS):
            response = await self.client.chat.completions.create(
                model=CHAT_MODEL, messages=conversation, tools=TOOLS, temperature=0.3
            )
            message = response.choices[0].message
            if not message.tool_calls:
                return {"answer": message.content or "", "tools_used": used}

            conversation.append(
                {
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [call.model_dump() for call in message.tool_calls],
                }
            )
            for call in message.tool_calls:
                used.append(call.function.name)
                result = await self.run_tool(call.function.name, call.function.arguments)
                conversation.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(result, default=str)[:12000],
                    }
                )

        return {
            "answer": "Sorry, I couldn't finish that. Try asking more simply.",
            "tools_used": used,
        }

    async def run_tool(self, name: str, raw_arguments: str) -> Any:
        try:
            arguments = json.loads(raw_arguments or "{}")
            handler = getattr(self, f"tool_{name}")
            return await handler(**arguments)
        except Exception as exc:  # noqa: BLE001 - report tool failures to the model
            logger.warning("CineBot tool %s failed: %s", name, exc)
            return {"error": f"{name} failed: {exc}"}

    # --- tools ---------------------------------------------------------------

    def _catalog(self):
        return [Movie.tmdb_synced_at.is_not(None), Movie.original_language.in_(self.languages)]

    async def tool_search_movies(
        self,
        title: str | None = None,
        language: str | None = None,
        genre: str | None = None,
        year: int | None = None,
        sort: str = "popularity",
    ) -> list[dict]:
        query = select(Movie).where(*self._catalog())
        if title:
            query = query.where(
                Movie.title.ilike(f"%{title}%") | Movie.original_title.ilike(f"%{title}%")
            )
        if language in self.languages:
            query = query.where(Movie.original_language == language)
        if genre:
            query = query.where(
                Movie.id.in_(
                    select(movie_genres.c.movie_id)
                    .join(Genre, Genre.id == movie_genres.c.genre_id)
                    .where(Genre.name.ilike(genre))
                )
            )
        if year:
            query = query.where(Movie.release_date.between(date(year, 1, 1), date(year, 12, 31)))
        order = {
            "rating": Movie.vote_average.desc().nulls_last(),
            "newest": Movie.release_date.desc().nulls_last(),
        }.get(sort, Movie.popularity.desc().nulls_last())
        if sort == "rating":
            query = query.where(Movie.vote_count >= 20)
        return [brief(m) for m in await self.session.scalars(query.order_by(order).limit(10))]

    async def tool_get_movie(self, movie_id: int) -> dict:
        movie = await self.session.get(Movie, movie_id)
        if movie is None:
            return {"error": "not found"}
        return brief(movie) | {
            "original_title": movie.original_title,
            "overview": movie.overview,
            "tagline": movie.tagline,
            "runtime_minutes": movie.runtime_minutes,
            "status": movie.status,
            "vote_count": movie.vote_count,
            "wikipedia_summary": movie.wikipedia_summary,
        }

    async def tool_upcoming_movies(self, language: str | None = None) -> list[dict]:
        query = select(Movie).where(*self._catalog(), Movie.release_date >= date.today())
        if language in self.languages:
            query = query.where(Movie.original_language == language)
        movies = await self.session.scalars(query.order_by(Movie.release_date).limit(15))
        return [brief(m) for m in movies]

    async def tool_my_history(self) -> dict:
        diary = await self.session.execute(
            select(DiaryEntry, Movie)
            .join(Movie, Movie.id == DiaryEntry.movie_id)
            .where(DiaryEntry.user_id == self.user_id)
            .order_by(DiaryEntry.watched_on.desc())
            .limit(30)
        )
        ratings = await self.session.execute(
            select(Movie.title, Rating.rating)
            .join(Rating, Rating.movie_id == Movie.id)
            .where(Rating.user_id == self.user_id)
            .order_by(Rating.rating.desc())
            .limit(50)
        )
        watchlist = await self.session.scalars(
            select(Movie.title)
            .join(WatchlistItem, WatchlistItem.movie_id == Movie.id)
            .where(WatchlistItem.user_id == self.user_id)
        )
        return {
            "diary": [
                {
                    "title": m.title,
                    "watched_on": e.watched_on.isoformat(),
                    "rating": float(e.rating) if e.rating is not None else None,
                    "review": e.review,
                }
                for e, m in diary
            ],
            "ratings": [{"title": t, "rating": float(r)} for t, r in ratings],
            "watchlist": list(watchlist),
        }

    async def tool_recommend(self) -> list[dict]:
        scored = await engine.for_user(self.session, self.user_id, self.languages, limit=10)
        return [brief(s.movie) | {"reason": s.reason} for s in scored]

    async def tool_web_search(self, query: str) -> dict:
        response = await self.client.chat.completions.create(
            model=SEARCH_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": f"{query}\n\nAnswer concisely with facts from the web. "
                    "Name your sources.",
                }
            ],
            tools=[{"type": "browser_search"}],
            max_completion_tokens=1500,
        )
        text = response.choices[0].message.content or ""
        return {"source": "web", "result": CITATION_MARK.sub("", text).strip()}
