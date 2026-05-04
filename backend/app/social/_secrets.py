"""Secret Manager helpers for LinkedIn tokens.

In prod we read/write the four LinkedIn secrets via the GCP SDK so the access
token can rotate at runtime. Locally we fall back to env vars (`LINKEDIN_*`)
so dev/dry-run testing doesn't require a GCP login.
"""

from __future__ import annotations

import logging
import os

from app.config import get_settings

log = logging.getLogger(__name__)


def _env_for(secret_id: str) -> str:
    """Map secret id `linkedin-access-token` → env var `LINKEDIN_ACCESS_TOKEN`."""
    return secret_id.upper().replace("-", "_")


def access_secret(secret_id: str) -> str:
    settings = get_settings()
    if settings.is_local:
        return os.environ.get(_env_for(secret_id), "")

    if not settings.gcp_project_id:
        raise RuntimeError("GCP_PROJECT_ID must be set in prod to access LinkedIn secrets")

    from google.cloud import secretmanager

    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{settings.gcp_project_id}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("utf-8")


def add_secret_version(secret_id: str, value: str) -> str:
    """Write a new secret version. Returns the version name."""
    settings = get_settings()
    if settings.is_local:
        os.environ[_env_for(secret_id)] = value
        log.info("local: wrote %s to env var %s", secret_id, _env_for(secret_id))
        return "local"

    if not settings.gcp_project_id:
        raise RuntimeError("GCP_PROJECT_ID must be set in prod to write LinkedIn secrets")

    from google.cloud import secretmanager

    client = secretmanager.SecretManagerServiceClient()
    parent = f"projects/{settings.gcp_project_id}/secrets/{secret_id}"
    version = client.add_secret_version(
        request={"parent": parent, "payload": {"data": value.encode("utf-8")}}
    )
    return version.name
