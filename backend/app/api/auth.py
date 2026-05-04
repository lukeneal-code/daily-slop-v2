"""Auth dependency for `/admin/*` routes.

Two modes:
- **Local** (`ENV=local`): a static bearer (`ADMIN_DEV_TOKEN`) is accepted. Empty
  token disables auth so `pytest` can hit the endpoint without setup.
- **Prod**: validates the OIDC ID token Cloud Scheduler attaches. Audience must
  match `settings.api_url` and `email` must equal `settings.scheduler_sa_email`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Header, HTTPException

from app.config import get_settings


async def verify_scheduler_or_dev_token(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    settings = get_settings()
    bearer = (authorization or "").removeprefix("Bearer ").strip()

    if settings.is_local:
        if not settings.admin_dev_token:
            return "anonymous-local"
        if bearer == settings.admin_dev_token:
            return "dev"
        raise HTTPException(status_code=401, detail="invalid admin dev token")

    if not bearer:
        raise HTTPException(status_code=401, detail="missing bearer token")

    # Lazy import — google-auth is only needed in prod.
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    # Accept the configured public URL plus any extra audiences (e.g. the raw
    # Cloud Run service URL pre-DNS-cutover). Comma-separated env var.
    audiences = [settings.api_url] + [
        a.strip() for a in (settings.extra_audiences or "").split(",") if a.strip()
    ]
    last_err: Exception | None = None
    claims = None
    for aud in audiences:
        try:
            claims = id_token.verify_oauth2_token(  # type: ignore[no-untyped-call]
                bearer, google_requests.Request(), audience=aud
            )
            break
        except ValueError as exc:
            last_err = exc
    if claims is None:
        raise HTTPException(
            status_code=401, detail=f"bad oidc token: {last_err}"
        ) from last_err

    if claims.get("email") != settings.scheduler_sa_email:
        raise HTTPException(status_code=403, detail="unrecognised principal")
    if not claims.get("email_verified"):
        raise HTTPException(status_code=403, detail="email not verified")
    return str(claims["email"])
