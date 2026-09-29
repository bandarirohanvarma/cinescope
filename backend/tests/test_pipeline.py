"""Pipeline unit tests. No network: HTTP is served by httpx.MockTransport."""

from datetime import date

import httpx
import pytest

from app.pipeline import movielens
from app.pipeline.tmdb import TMDBClient, movie_fields
from app.pipeline.wikipedia import WikipediaClient


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Toy Story (1995)", ("Toy Story", 1995)),
        ("Matrix, The (1999)", ("The Matrix", 1999)),
        (
            "Fabuleux destin d'Amélie Poulain, Le (2001)",
            ("Le Fabuleux destin d'Amélie Poulain", 2001),
        ),
        ("Enfants du paradis, Les (1945)", ("Les Enfants du paradis", 1945)),
        ("Stranger Things (2016-)", ("Stranger Things", 2016)),
        ("Hyena Road", ("Hyena Road", None)),
    ],
)
def test_parse_title(raw, expected):
    assert movielens.parse_title(raw) == expected


def test_read_movies_joins_links_and_drops_duplicate_tmdb_ids(tmp_path):
    (tmp_path / "movies.csv").write_text(
        "movieId,title,genres\n"
        "1,Toy Story (1995),Animation\n"
        '2,"Matrix, The (1999)",Action\n'
        "3,Duplicate (1999),Action\n"
        "4,No Link (2000),Drama\n",
        encoding="utf-8",
    )
    (tmp_path / "links.csv").write_text(
        "movieId,imdbId,tmdbId\n1,0114709,862\n2,0133093,603\n3,0133093,603\n4,0000001,\n",
        encoding="utf-8",
    )

    assert movielens.read_movies(tmp_path) == [
        {"movielens_id": 1, "title": "Toy Story", "tmdb_id": 862},
        {"movielens_id": 2, "title": "The Matrix", "tmdb_id": 603},
        {"movielens_id": 3, "title": "Duplicate", "tmdb_id": None},
        {"movielens_id": 4, "title": "No Link", "tmdb_id": None},
    ]


def test_movie_fields_maps_tmdb_payload():
    payload = {
        "id": 603,
        "imdb_id": "tt0133093",
        "title": "The Matrix",
        "original_title": "The Matrix",
        "original_language": "en",
        "overview": "A hacker learns the truth.",
        "tagline": "",
        "release_date": "1999-03-31",
        "runtime": 136,
        "status": "Released",
        "poster_path": "/p.jpg",
        "backdrop_path": None,
        "popularity": 80.5,
        "vote_average": 8.2,
        "vote_count": 26000,
        "external_ids": {"wikidata_id": "Q83495"},
    }

    fields = movie_fields(payload)

    assert fields["tmdb_id"] == 603
    assert fields["release_date"] == date(1999, 3, 31)
    assert fields["wikidata_id"] == "Q83495"
    assert fields["tagline"] is None  # empty strings become NULL


def test_movie_fields_handles_missing_release_date():
    fields = movie_fields({"id": 1, "title": "Untitled Project", "release_date": ""})
    assert fields["release_date"] is None
    assert fields["wikidata_id"] is None


async def test_tmdb_client_retries_after_rate_limit():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"id": 603, "title": "The Matrix"})

    async with TMDBClient("token", transport=httpx.MockTransport(handler)) as tmdb:
        details = await tmdb.movie_details(603)

    assert details == {"id": 603, "title": "The Matrix"}
    assert calls == ["/3/movie/603", "/3/movie/603"]


async def test_tmdb_client_returns_none_for_missing_movie():
    transport = httpx.MockTransport(lambda request: httpx.Response(404))
    async with TMDBClient("token", transport=transport) as tmdb:
        assert await tmdb.movie_details(999999999) is None


async def test_tmdb_paged_ids_stops_at_total_pages_and_dedupes():
    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        results = [{"id": 1}, {"id": 2}] if page == 1 else [{"id": 2}, {"id": 3}]
        return httpx.Response(200, json={"results": results, "total_pages": 2})

    async with TMDBClient("token", transport=httpx.MockTransport(handler)) as tmdb:
        assert await tmdb.movie_list("upcoming", pages=10, region="US") == [1, 2, 3]


async def test_wikipedia_resolves_titles_and_skips_disambiguation():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "www.wikidata.org":
            return httpx.Response(
                200,
                json={
                    "entities": {
                        "Q83495": {"sitelinks": {"enwiki": {"title": "The Matrix"}}},
                        "Q1": {"sitelinks": {}},
                    }
                },
            )
        if request.url.path.endswith("The_Matrix"):
            return httpx.Response(200, json={"type": "standard", "extract": "A 1999 film."})
        return httpx.Response(200, json={"type": "disambiguation", "extract": "May refer to"})

    async with WikipediaClient("test-agent", transport=httpx.MockTransport(handler)) as wiki:
        assert await wiki.enwiki_titles(["Q83495", "Q1"]) == {"Q83495": "The Matrix"}
        assert await wiki.summary("The Matrix") == "A 1999 film."
        assert await wiki.summary("Matrix") is None
