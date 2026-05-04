"""Tests for the LinkedIn HTTP client.

Uses respx to mock the LinkedIn endpoints. Verifies:
- Image upload is the documented two-step (initialize → PUT bytes).
- Post payload shape matches the Posts API schema.
- A 401 on a post triggers refresh_token + retry, and the new token is
  written to "Secret Manager" (env var in local mode).
"""

from __future__ import annotations

import os

import httpx
import pytest
import respx

from app.config import get_settings
from app.social import linkedin


@pytest.fixture(autouse=True)
def _seed_creds(monkeypatch):
    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("LINKEDIN_CLIENT_ID", "client123")
    monkeypatch.setenv("LINKEDIN_CLIENT_SECRET", "secret456")
    monkeypatch.setenv("LINKEDIN_ACCESS_TOKEN", "old-access")
    monkeypatch.setenv("LINKEDIN_REFRESH_TOKEN", "refresh789")
    get_settings.cache_clear()
    yield
    for k in (
        "LINKEDIN_CLIENT_ID",
        "LINKEDIN_CLIENT_SECRET",
        "LINKEDIN_ACCESS_TOKEN",
        "LINKEDIN_REFRESH_TOKEN",
    ):
        os.environ.pop(k, None)
    get_settings.cache_clear()


@pytest.mark.asyncio
@respx.mock
async def test_post_with_image_happy_path() -> None:
    init_route = respx.post(
        "https://api.linkedin.com/rest/images?action=initializeUpload"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "value": {
                    "uploadUrl": "https://upload.linkedin.com/abc",
                    "image": "urn:li:image:IMAGE_URN",
                }
            },
        )
    )
    upload_route = respx.put("https://upload.linkedin.com/abc").mock(
        return_value=httpx.Response(201)
    )
    post_route = respx.post("https://api.linkedin.com/rest/posts").mock(
        return_value=httpx.Response(
            201, headers={"x-restli-id": "urn:li:share:POST_URN"}
        )
    )

    urn = await linkedin.post_with_image(
        author_urn="urn:li:organization:1",
        commentary="In the news today...\n• A\n• B\n• C\n\nhttps://dailyslop.co.uk",
        image_bytes=b"\x89PNG\r\n\x1a\n",
    )
    assert urn == "urn:li:share:POST_URN"
    assert init_route.call_count == 1
    assert upload_route.call_count == 1
    assert post_route.call_count == 1

    body = post_route.calls.last.request.read()
    import json as _json

    payload = _json.loads(body)
    assert payload["author"] == "urn:li:organization:1"
    assert payload["lifecycleState"] == "PUBLISHED"
    assert payload["visibility"] == "PUBLIC"
    assert payload["content"]["media"]["id"] == "urn:li:image:IMAGE_URN"


@pytest.mark.asyncio
@respx.mock
async def test_401_triggers_refresh_and_retry() -> None:
    respx.post(
        "https://api.linkedin.com/rest/images?action=initializeUpload"
    ).mock(
        side_effect=[
            httpx.Response(401, json={"message": "expired"}),
            httpx.Response(
                200,
                json={
                    "value": {
                        "uploadUrl": "https://upload.linkedin.com/abc",
                        "image": "urn:li:image:NEW",
                    }
                },
            ),
        ]
    )
    refresh_route = respx.post("https://www.linkedin.com/oauth/v2/accessToken").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "new-access",
                "refresh_token": "new-refresh",
                "expires_in": 5184000,
            },
        )
    )
    respx.put("https://upload.linkedin.com/abc").mock(
        return_value=httpx.Response(201)
    )
    respx.post("https://api.linkedin.com/rest/posts").mock(
        return_value=httpx.Response(
            201, headers={"x-restli-id": "urn:li:share:OK"}
        )
    )

    urn = await linkedin.post_with_image(
        author_urn="urn:li:organization:1",
        commentary="x",
        image_bytes=b"x",
    )
    assert urn == "urn:li:share:OK"
    assert refresh_route.call_count == 1
    # New access token persisted to env (local-mode Secret Manager fallback).
    assert os.environ["LINKEDIN_ACCESS_TOKEN"] == "new-access"
    assert os.environ["LINKEDIN_REFRESH_TOKEN"] == "new-refresh"


@pytest.mark.asyncio
@respx.mock
async def test_no_access_token_raises() -> None:
    os.environ.pop("LINKEDIN_ACCESS_TOKEN", None)
    get_settings.cache_clear()
    with pytest.raises(linkedin.LinkedInError, match="no access token"):
        await linkedin.post_with_image(
            author_urn="urn:li:organization:1",
            commentary="x",
            image_bytes=b"x",
        )
