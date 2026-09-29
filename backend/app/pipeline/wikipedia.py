"""Resolve Wikidata ids to English Wikipedia articles and fetch their summaries."""

import asyncio
import logging
from typing import Any
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
SUMMARY_API = "https://en.wikipedia.org/api/rest_v1/page/summary/"
WIKIDATA_BATCH = 50  # wbgetentities accepts up to 50 ids per call


class WikipediaUnavailable(RuntimeError):
    """Wikimedia kept refusing (throttling); retry the job later."""


class WikipediaClient:
    def __init__(
        self,
        user_agent: str,
        concurrency: int = 5,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._http = httpx.AsyncClient(
            headers={"User-Agent": user_agent},
            timeout=30,
            follow_redirects=True,
            transport=transport,
        )
        self._limit = asyncio.Semaphore(concurrency)

    async def __aenter__(self) -> "WikipediaClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._http.aclose()

    async def _get_json(self, url: str, **params: Any) -> dict[str, Any] | None:
        for attempt in range(4):
            async with self._limit:
                try:
                    response = await self._http.get(url, params=params or None)
                except httpx.TransportError as exc:
                    logger.warning("Wikimedia transport error: %s", exc)
                    await asyncio.sleep(2**attempt)
                    continue
            if response.status_code == 404:
                return None
            # Wikimedia answers 403 or 429 when throttling.
            if response.status_code in (403, 429) or response.status_code >= 500:
                await asyncio.sleep(float(response.headers.get("Retry-After", 2 ** (attempt + 1))))
                continue
            if response.is_error:
                logger.warning("Wikimedia %s -> %s", url, response.status_code)
                return None
            return response.json()
        raise WikipediaUnavailable(url)

    async def enwiki_titles(self, wikidata_ids: list[str]) -> dict[str, str]:
        """Map Wikidata ids (Q-numbers) to English Wikipedia article titles."""
        batches = [
            wikidata_ids[i : i + WIKIDATA_BATCH]
            for i in range(0, len(wikidata_ids), WIKIDATA_BATCH)
        ]
        # Sequential on purpose: Wikidata throttles parallel bulk lookups.
        results = [
            await self._get_json(
                WIKIDATA_API,
                action="wbgetentities",
                ids="|".join(batch),
                props="sitelinks",
                sitefilter="enwiki",
                format="json",
            )
            for batch in batches
        ]
        titles: dict[str, str] = {}
        for data in results:
            for qid, entity in ((data or {}).get("entities") or {}).items():
                link = (entity.get("sitelinks") or {}).get("enwiki")
                if link:
                    titles[qid] = link["title"]
        return titles

    async def summary(self, title: str) -> str | None:
        """Plain-text lead section of an English Wikipedia article."""
        data = await self._get_json(SUMMARY_API + quote(title.replace(" ", "_"), safe=""))
        if not data or data.get("type") == "disambiguation":
            return None
        return data.get("extract") or None
