USER = {"email": "Ravi@Example.com", "password": "correct-horse", "display_name": "Ravi"}


async def register(client, **overrides):
    return await client.post("/api/v1/auth/register", json=USER | overrides)


async def login(client, email=USER["email"], password=USER["password"]):
    return await client.post("/api/v1/auth/login", data={"username": email, "password": password})


def bearer(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def test_register_then_fetch_profile_with_telugu_hindi_defaults(client):
    response = await register(client)
    assert response.status_code == 201

    me = await client.get("/api/v1/users/me", headers=bearer(response.json()))

    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "ravi@example.com"
    assert body["preferences"]["region"] == "IN"
    assert body["preferences"]["languages"] == ["te", "hi"]


async def test_register_rejects_duplicate_email_case_insensitively(client):
    await register(client)
    response = await register(client, email="RAVI@example.com")
    assert response.status_code == 409


async def test_register_rejects_short_password(client):
    response = await register(client, password="short")
    assert response.status_code == 422


async def test_login_success_and_wrong_password(client):
    await register(client)

    assert (await login(client)).status_code == 200
    assert (await login(client, password="wrong-password")).status_code == 401
    assert (await login(client, email="nobody@example.com")).status_code == 401


async def test_refresh_issues_new_tokens_and_rejects_access_token(client):
    tokens = (await register(client)).json()

    refreshed = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    wrong_type = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]}
    )

    assert refreshed.status_code == 200
    assert wrong_type.status_code == 401


async def test_me_requires_valid_token(client):
    assert (await client.get("/api/v1/users/me")).status_code == 401
    bad = {"Authorization": "Bearer not-a-token"}
    assert (await client.get("/api/v1/users/me", headers=bad)).status_code == 401


async def test_update_preferences(client):
    tokens = (await register(client)).json()

    response = await client.patch(
        "/api/v1/users/me/preferences",
        json={"languages": ["te"], "region": "in", "favorite_genre_ids": [28]},
        headers=bearer(tokens),
    )

    assert response.status_code == 200
    prefs = response.json()["preferences"]
    assert prefs["languages"] == ["te"]
    assert prefs["region"] == "IN"
    assert prefs["favorite_genre_ids"] == [28]
    assert prefs["email_reminders"] is True  # untouched
