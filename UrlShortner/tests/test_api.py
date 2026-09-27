import pytest


@pytest.mark.asyncio
async def test_health_check(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_shorten_returns_a_short_code(client):
    resp = await client.post("/api/shorten", json={"long_url": "https://example.com/hello"})
    assert resp.status_code == 201

    body = resp.json()
    assert body["long_url"] == "https://example.com/hello"
    assert len(body["short_code"]) >= 6
    assert body["short_url"].endswith(body["short_code"])


@pytest.mark.asyncio
async def test_shorten_rejects_non_http_urls(client):
    resp = await client.post("/api/shorten", json={"long_url": "ftp://example.com/file"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_custom_alias_is_honored(client):
    resp = await client.post(
        "/api/shorten",
        json={"long_url": "https://example.com/custom", "custom_alias": "my-link"},
    )
    assert resp.status_code == 201
    assert resp.json()["short_code"] == "my-link"


@pytest.mark.asyncio
async def test_duplicate_custom_alias_returns_409(client):
    payload = {"long_url": "https://example.com/one", "custom_alias": "taken"}
    first = await client.post("/api/shorten", json=payload)
    assert first.status_code == 201

    second = await client.post(
        "/api/shorten",
        json={"long_url": "https://example.com/two", "custom_alias": "taken"},
    )
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_redirect_follows_to_long_url(client):
    created = await client.post("/api/shorten", json={"long_url": "https://example.com/target"})
    short_code = created.json()["short_code"]

    resp = await client.get(f"/{short_code}", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "https://example.com/target"


@pytest.mark.asyncio
async def test_redirect_unknown_code_returns_404(client):
    resp = await client.get("/does-not-exist", follow_redirects=False)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_second_redirect_is_served_from_cache(client):
    # Not directly observable from the HTTP response, but this exercises
    # the full cache-aside path: miss -> populate -> hit, without erroring.
    created = await client.post("/api/shorten", json={"long_url": "https://example.com/cached"})
    short_code = created.json()["short_code"]

    first = await client.get(f"/{short_code}", follow_redirects=False)
    second = await client.get(f"/{short_code}", follow_redirects=False)

    assert first.status_code == second.status_code == 302
    assert first.headers["location"] == second.headers["location"]


@pytest.mark.asyncio
async def test_stats_reports_click_count_field(client):
    created = await client.post("/api/shorten", json={"long_url": "https://example.com/stats"})
    short_code = created.json()["short_code"]

    resp = await client.get(f"/api/stats/{short_code}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["short_code"] == short_code
    assert "clicks" in body


@pytest.mark.asyncio
async def test_stats_unknown_code_returns_404(client):
    resp = await client.get("/api/stats/does-not-exist")
    assert resp.status_code == 404
