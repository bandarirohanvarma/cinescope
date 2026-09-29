"""Minimal async client for the TMDB v3 API."""

import asyncio
import logging
from datetime import date
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.themoviedb.org/3"
MAX_RETRIES = 5


class TMDBError(RuntimeError):
    pass


class TMDBClient:
    def __init__(
        self,
        token: str,
        concurrency: int = 10,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._http = httpx.AsyncClient(
            base_url=BASE_URL,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=30,
            transport=transport,
        )
        self._limit = asyncio.Semaphore(concurrency)

    async def __aenter__(self) -> "TMDBClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._http.aclose()

    async def get(self, path: str, **params: Any) -> dict[str, Any] | None:
        """GET a TMDB resource. Returns None on 404; retries on 429 and 5xx."""
        for attempt in range(MAX_RETRIES):
            async with self._limit:
                try:
                    response = await self._http.get(path, params=params)
                except httpx.TransportError as exc:
                    logger.warning("TMDB %s transport error: %s", path, exc)
                    await asyncio.sleep(2**attempt)
                    continue

            if response.status_code == 404:
                return None
            if response.status_code == 429 or response.status_code >= 500:
                delay = float(response.headers.get("Retry-After", 2**attempt))
                logger.warning("TMDB %s -> %s, retrying in %ss", path, response.status_code, delay)
                await asyncio.sleep(delay)
                continue
            if response.is_error:
                raise TMDBError(f"TMDB {path} -> {response.status_code}: {response.text[:200]}")
            return response.json()

        raise TMDBError(f"TMDB {path} failed after {MAX_RETRIES} attempts")

    async def movie_details(self, tmdb_id: int) -> dict[str, Any] | None:
        return await self.get(f"/movie/{tmdb_id}", append_to_response="external_ids")

    async def genres(self) -> list[dict[str, Any]]:
        data = await self.get("/genre/movie/list")
        return data["genres"] if data else []

    async def movie_list(self, name: str, pages: int, region: str | None = None) -> list[int]:
        """TMDB ids from a paged list: upcoming, now_playing, popular, top_rated."""
        params = {"region": region} if region else {}
        return await self._paged_ids(f"/movie/{name}", pages, **params)

    async def trending(self, pages: int, window: str = "week") -> list[int]:
        return await self._paged_ids(f"/trending/movie/{window}", pages)

    async def discover(self, pages: int, **filters: Any) -> list[int]:
        """TMDB ids from /discover/movie, e.g. with_original_language="te"."""
        return await self._paged_ids("/discover/movie", pages, **filters)

    async def changed_movie_ids(self, start: date, end: date) -> list[int]:
        """Ids of movies edited on TMDB between two dates (max 14 days apart)."""
        return await self._paged_ids(
            "/movie/changes", pages=1000, start_date=start.isoformat(), end_date=end.isoformat()
        )

    async def _paged_ids(self, path: str, pages: int, **params: Any) -> list[int]:
        first = await self.get(path, page=1, **params) or {"results": [], "total_pages": 0}
        last_page = min(pages, first.get("total_pages", 1), 500)
        rest = await asyncio.gather(
            *(self.get(path, page=page, **params) for page in range(2, last_page + 1))
        )
        ids: list[int] = []
        for data in [first, *rest]:
            ids.extend(item["id"] for item in (data or {}).get("results", []) if "id" in item)
        return list(dict.fromkeys(ids))  # de-duplicate, keep order


def movie_fields(details: dict[str, Any]) -> dict[str, Any]:
    """Map a TMDB /movie/{id} payload to columns on the movies table."""
    release = details.get("release_date") or None
    return {
        "tmdb_id": details["id"],
        "imdb_id": details.get("imdb_id") or None,
        "wikidata_id": (details.get("external_ids") or {}).get("wikidata_id") or None,
        "title": details.get("title") or details.get("original_title") or "Untitled",
        "original_title": details.get("original_title"),
        "original_language": details.get("original_language"),
        "overview": details.get("overview") or None,
        "tagline": details.get("tagline") or None,
        "release_date": date.fromisoformat(release) if release else None,
        "runtime_minutes": details.get("runtime") or None,
        "status": details.get("status"),
        "poster_path": details.get("poster_path"),
        "backdrop_path": details.get("backdrop_path"),
        "popularity": details.get("popularity"),
        "vote_average": details.get("vote_average"),
        "vote_count": details.get("vote_count"),
    }
