"""End-to-end orchestrator for the daily LinkedIn post.

Flow:
1. Look up `front_page_picks` for the target date and load the three articles.
2. Idempotency: if a `linkedin_posts` row with status='sent' already exists for
   the date, no-op.
3. Compose the commentary text.
4. Fetch the headline image bytes.
5. Post to LinkedIn (or log + skip in dry-run mode).
6. Persist a `linkedin_posts` row with the outcome.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Article, FrontPagePick, ImageAsset, LinkedInPost
from app.db.session import session_factory
from app.social import linkedin
from app.social.compose import compose_post, ordered_picks

log = logging.getLogger(__name__)


@dataclass
class PostResult:
    publish_date: date
    status: str  # sent | failed | skipped | already_sent
    post_urn: str | None
    article_ids: list[int]
    error: str | None = None


async def _load_picks(
    session: AsyncSession, publish_date: date
) -> dict[str, Article]:
    rows = (
        await session.execute(
            select(FrontPagePick).where(FrontPagePick.publish_date == publish_date)
        )
    ).scalars().all()
    out: dict[str, Article] = {}
    for row in rows:
        article = await session.get(Article, row.article_id)
        if article is not None:
            out[row.slot] = article
    return out


async def _fetch_image_bytes(image: ImageAsset) -> bytes:
    """Download the image from its public URL.

    Works in both local (FastAPI static mount) and prod (CDN). Avoids pulling
    `google-cloud-storage` for a one-shot read.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(image.public_url)
    if response.status_code >= 300:
        raise RuntimeError(
            f"image fetch failed: {response.status_code} {image.public_url}"
        )
    return response.content


async def post_today_to_linkedin(publish_date: date) -> PostResult:
    settings = get_settings()
    Session = session_factory()  # noqa: N806 — SQLAlchemy convention

    async with Session() as session:
        existing = await session.get(LinkedInPost, publish_date)
        if existing is not None and existing.status == "sent":
            log.info(
                "linkedin: already posted for %s (urn=%s)",
                publish_date,
                existing.post_urn,
            )
            return PostResult(
                publish_date=publish_date,
                status="already_sent",
                post_urn=existing.post_urn,
                article_ids=list(existing.article_ids),
            )

        picks = await _load_picks(session, publish_date)
        articles = ordered_picks(picks)
        if not articles:
            log.warning("linkedin: no front-page picks for %s — skipping", publish_date)
            row = LinkedInPost(
                publish_date=publish_date,
                post_urn=None,
                post_text="",
                image_asset_id=None,
                article_ids=[],
                status="skipped",
                error="no front_page_picks",
            )
            await session.merge(row)
            await session.commit()
            return PostResult(
                publish_date=publish_date,
                status="skipped",
                post_urn=None,
                article_ids=[],
                error="no front_page_picks",
            )

        commentary = compose_post(picks, site_url=settings.site_url)
        article_ids = [a.id for a in articles]
        headline_article = articles[0]
        image_asset_id = headline_article.image_asset_id

        if not settings.linkedin_org_urn:
            raise RuntimeError("LINKEDIN_ORG_URN is not configured")

        if settings.linkedin_dry_run:
            log.info(
                "linkedin DRY_RUN — would post to %s:\n%s",
                settings.linkedin_org_urn,
                commentary,
            )
            row = LinkedInPost(
                publish_date=publish_date,
                post_urn="dry-run",
                post_text=commentary,
                image_asset_id=image_asset_id,
                article_ids=article_ids,
                status="sent",
                error=None,
            )
            await session.merge(row)
            await session.commit()
            return PostResult(
                publish_date=publish_date,
                status="sent",
                post_urn="dry-run",
                article_ids=article_ids,
            )

        if headline_article.image_asset is None:
            raise RuntimeError(
                f"headline article {headline_article.id} has no image_asset"
            )
        image_bytes = await _fetch_image_bytes(headline_article.image_asset)

    # Network call outside the session.
    try:
        post_urn = await linkedin.post_with_image(
            author_urn=settings.linkedin_org_urn,
            commentary=commentary,
            image_bytes=image_bytes,
        )
    except Exception as exc:
        log.exception("linkedin post failed for %s", publish_date)
        async with Session() as session:
            await session.merge(
                LinkedInPost(
                    publish_date=publish_date,
                    post_urn=None,
                    post_text=commentary,
                    image_asset_id=image_asset_id,
                    article_ids=article_ids,
                    status="failed",
                    error=str(exc)[:2000],
                )
            )
            await session.commit()
        raise

    async with Session() as session:
        await session.merge(
            LinkedInPost(
                publish_date=publish_date,
                post_urn=post_urn,
                post_text=commentary,
                image_asset_id=image_asset_id,
                article_ids=article_ids,
                status="sent",
                error=None,
            )
        )
        await session.commit()

    log.info("linkedin: posted for %s (urn=%s)", publish_date, post_urn)
    return PostResult(
        publish_date=publish_date,
        status="sent",
        post_urn=post_urn,
        article_ids=article_ids,
    )
