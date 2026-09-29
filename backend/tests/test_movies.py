def titles(response):
    return [movie["title"] for movie in response.json()["items"]]


async def test_catalog_only_has_telugu_and_hindi_by_popularity(client, catalog):
    response = await client.get("/api/v1/movies")

    assert response.status_code == 200
    assert titles(response) == ["RRR", "Baahubali: The Beginning", "3 Idiots", "Future Telugu Film"]
    assert response.json()["total"] == 4


async def test_filter_by_language_and_reject_other_languages(client, catalog):
    hindi = await client.get("/api/v1/movies", params={"language": "hi"})
    english = await client.get("/api/v1/movies", params={"language": "en"})

    assert titles(hindi) == ["3 Idiots"]
    assert english.status_code == 400


async def test_search_is_case_insensitive_and_partial(client, catalog):
    response = await client.get("/api/v1/movies", params={"q": "baahu"})
    assert titles(response) == ["Baahubali: The Beginning"]


async def test_search_does_not_leak_other_languages(client, catalog):
    response = await client.get("/api/v1/movies", params={"q": "matrix"})
    assert titles(response) == []


async def test_filter_by_genre_and_year(client, catalog):
    action = await client.get("/api/v1/movies", params={"genre_id": 28})
    year = await client.get("/api/v1/movies", params={"year": 2009})

    assert titles(action) == ["RRR", "Baahubali: The Beginning"]
    assert titles(year) == ["3 Idiots"]


async def test_sort_by_rating_skips_movies_with_few_votes(client, catalog):
    response = await client.get("/api/v1/movies", params={"sort": "rating"})
    assert titles(response) == ["3 Idiots", "RRR", "Baahubali: The Beginning"]


async def test_pagination(client, catalog):
    response = await client.get("/api/v1/movies", params={"page": 2, "size": 3})
    body = response.json()
    assert titles(response) == ["Future Telugu Film"]
    assert (body["total"], body["page"], body["size"]) == (4, 2, 3)


async def test_upcoming_lists_future_releases_soonest_first(client, catalog):
    response = await client.get("/api/v1/movies/upcoming")
    assert titles(response) == ["Future Telugu Film"]


async def test_movie_detail_and_404(client, catalog):
    found = await client.get("/api/v1/movies/2")
    missing = await client.get("/api/v1/movies/999")

    assert found.status_code == 200
    assert found.json()["title"] == "RRR"
    assert found.json()["genres"] == [{"id": 28, "name": "Action"}]
    assert missing.status_code == 404


async def test_genres_sorted_by_name(client, catalog):
    response = await client.get("/api/v1/genres")
    assert [g["name"] for g in response.json()] == ["Action", "Comedy"]
