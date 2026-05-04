"""LinkedIn REST API client.

Posts to a company page using the Posts + Images APIs (`/rest/posts`,
`/rest/images`). Access tokens expire after 60 days; on 401 we use the
refresh token to mint a new access token and write the new value back to
Secret Manager so subsequent runs (and other Cloud Run instances) see it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import get_settings
from app.social import _secrets

log = logging.getLogger(__name__)

REST_BASE = "https://api.linkedin.com/rest"
OAUTH_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"


class LinkedInError(RuntimeError):
    pass


@dataclass
class LinkedInCreds:
    client_id: str
    client_secret: str
    access_token: str
    refresh_token: str


def _load_creds() -> LinkedInCreds:
    settings = get_settings()
    return LinkedInCreds(
        client_id=_secrets.access_secret(settings.linkedin_client_id_secret),
        client_secret=_secrets.access_secret(settings.linkedin_client_secret_secret),
        access_token=_secrets.access_secret(settings.linkedin_access_token_secret),
        refresh_token=_secrets.access_secret(settings.linkedin_refresh_token_secret),
    )


async def _refresh_access_token(creds: LinkedInCreds) -> str:
    """Exchange the refresh token for a new access token and persist it."""
    settings = get_settings()
    if not creds.refresh_token:
        raise LinkedInError(
            "no refresh token available — re-run scripts/linkedin_oauth.py"
        )
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            OAUTH_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": creds.refresh_token,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if response.status_code != 200:
        raise LinkedInError(f"refresh failed: {response.status_code} {response.text}")
    body = response.json()
    new_access = body["access_token"]
    _secrets.add_secret_version(settings.linkedin_access_token_secret, new_access)
    if "refresh_token" in body:
        _secrets.add_secret_version(
            settings.linkedin_refresh_token_secret, body["refresh_token"]
        )
    log.info("linkedin: refreshed access token")
    return str(new_access)


def _headers(token: str) -> dict[str, str]:
    settings = get_settings()
    return {
        "Authorization": f"Bearer {token}",
        "LinkedIn-Version": settings.linkedin_api_version,
        "X-Restli-Protocol-Version": "2.0.0",
    }


class LinkedInClient:
    """Thin wrapper around the Posts + Images REST APIs.

    Reuses one `httpx.AsyncClient` across upload + post calls, refreshes the
    access token on 401 and retries the failed call once.
    """

    def __init__(self, creds: LinkedInCreds) -> None:
        self._creds = creds
        self._token = creds.access_token

    async def __aenter__(self) -> LinkedInClient:
        self._http = httpx.AsyncClient(timeout=60)
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self._http.aclose()

    async def _request(
        self, method: str, url: str, *, _retried: bool = False, **kwargs: Any
    ) -> httpx.Response:
        kwargs.setdefault("headers", {}).update(_headers(self._token))
        response = await self._http.request(method, url, **kwargs)
        if response.status_code == 401 and not _retried:
            log.info("linkedin: 401, refreshing access token and retrying once")
            self._token = await _refresh_access_token(self._creds)
            kwargs["headers"].update(_headers(self._token))
            return await self._request(method, url, _retried=True, **kwargs)
        return response

    async def upload_image(self, *, owner_urn: str, image_bytes: bytes) -> str:
        """Two-step image upload. Returns the `urn:li:image:...` asset URN."""
        init = await self._request(
            "POST",
            f"{REST_BASE}/images?action=initializeUpload",
            json={"initializeUploadRequest": {"owner": owner_urn}},
        )
        if init.status_code >= 300:
            raise LinkedInError(f"image init failed: {init.status_code} {init.text}")
        init_body = init.json()["value"]
        upload_url = init_body["uploadUrl"]
        image_urn = init_body["image"]

        # The upload PUT does NOT use the REST headers — only the bearer token.
        put = await self._http.put(
            upload_url,
            content=image_bytes,
            headers={"Authorization": f"Bearer {self._token}"},
        )
        if put.status_code >= 300:
            raise LinkedInError(f"image upload failed: {put.status_code} {put.text}")
        return str(image_urn)

    async def create_post(
        self, *, author_urn: str, commentary: str, image_urn: str
    ) -> str:
        """Create a published post on the company page. Returns the post URN."""
        body = {
            "author": author_urn,
            "commentary": commentary,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "content": {"media": {"id": image_urn}},
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        response = await self._request("POST", f"{REST_BASE}/posts", json=body)
        if response.status_code >= 300:
            raise LinkedInError(f"post failed: {response.status_code} {response.text}")
        post_urn = response.headers.get("x-restli-id") or response.headers.get(
            "X-RestLi-Id"
        )
        if not post_urn:
            data = response.json() if response.content else {}
            post_urn = data.get("id") or data.get("urn") or ""
        return str(post_urn)


async def post_with_image(
    *, author_urn: str, commentary: str, image_bytes: bytes
) -> str:
    """Convenience: upload + post in one call. Returns the post URN."""
    creds = _load_creds()
    if not creds.access_token:
        raise LinkedInError(
            "no access token — run scripts/linkedin_oauth.py to seed one"
        )
    async with LinkedInClient(creds) as client:
        image_urn = await client.upload_image(
            owner_urn=author_urn, image_bytes=image_bytes
        )
        return await client.create_post(
            author_urn=author_urn, commentary=commentary, image_urn=image_urn
        )
