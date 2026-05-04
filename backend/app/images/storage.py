"""Persist generated images.

Local mode (FAKE_LLM / dev): write to `images_local_dir`, expose under
`images_public_base_url/<date>/<slug>.png` by FastAPI's StaticFiles.

Cloud mode: upload to the configured GCS bucket with public-read ACL.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.config import Settings, get_settings


@dataclass(frozen=True)
class StoredImage:
    public_url: str
    gcs_uri: str | None
    width: int
    height: int


_DEFAULT_DIMS = {
    "16:9": (1792, 1024),
    "1:1": (1024, 1024),
}


async def _save_local(
    *, data: bytes, publish_date: date, slug: str, settings: Settings
) -> StoredImage:
    base = Path(settings.images_local_dir) / publish_date.isoformat()
    base.mkdir(parents=True, exist_ok=True)
    out = base / f"{slug}.png"
    await asyncio.to_thread(out.write_bytes, data)
    public_url = f"{settings.images_public_base_url.rstrip('/')}/{publish_date.isoformat()}/{slug}.png"
    return StoredImage(public_url=public_url, gcs_uri=None, width=0, height=0)


async def _save_gcs(
    *,
    data: bytes,
    publish_date: date,
    slug: str,
    settings: Settings,
) -> StoredImage:
    # Lazy import so local dev / tests don't pull google-cloud-storage onto the path.
    from google.cloud import storage  # type: ignore[attr-defined]

    def _blocking() -> StoredImage:
        client = storage.Client(project=None)
        bucket = client.bucket(settings.images_bucket)
        path = f"{publish_date.isoformat()}/{slug}.png"
        blob = bucket.blob(path)
        blob.cache_control = "public, max-age=31536000, immutable"
        blob.upload_from_string(data, content_type="image/png")
        # Bucket is public-read in prod (uniform IAM grants allUsers reader),
        # so the canonical URL is fine to expose.
        public_url = f"{settings.images_public_base_url.rstrip('/')}/{path}"
        gcs_uri = f"gs://{settings.images_bucket}/{path}"
        return StoredImage(public_url=public_url, gcs_uri=gcs_uri, width=0, height=0)

    return await asyncio.to_thread(_blocking)


async def store_image(
    *,
    data: bytes,
    publish_date: date,
    slug: str,
    aspect_ratio: str,
    settings: Settings | None = None,
) -> StoredImage:
    s = settings or get_settings()
    width, height = _DEFAULT_DIMS.get(aspect_ratio, _DEFAULT_DIMS["1:1"])
    if s.is_local or s.fake_llm:
        stored = await _save_local(data=data, publish_date=publish_date, slug=slug, settings=s)
    else:
        stored = await _save_gcs(data=data, publish_date=publish_date, slug=slug, settings=s)
    return StoredImage(
        public_url=stored.public_url,
        gcs_uri=stored.gcs_uri,
        width=width,
        height=height,
    )
