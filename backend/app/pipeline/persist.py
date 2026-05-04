"""Persist a single graph invocation's output to the DB."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.state import PipelineState
from app.db.models import AgentRun, Article, FrontPagePick, ImageAsset
from app.utils.slug import base_slug, disambiguate

log = logging.getLogger(__name__)


async def _slug_taken(
    session: AsyncSession, *, publish_date: date, section: str
) -> set[str]:
    rows = (
        await session.execute(
            select(Article.slug).where(
                Article.publish_date == publish_date, Article.section == section
            )
        )
    ).scalars().all()
    return set(rows)


async def upsert_run(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    publish_date: date,
    langfuse_trace_id: str | None = None,
) -> AgentRun:
    existing = await session.get(AgentRun, run_id)
    if existing:
        return existing
    run = AgentRun(
        id=run_id,
        publish_date=publish_date,
        status="running",
        langfuse_trace_id=langfuse_trace_id,
    )
    session.add(run)
    await session.flush()
    return run


async def finish_run(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    total_articles: int,
    rejected_count: int,
    status: str = "completed",
) -> None:
    run = await session.get(AgentRun, run_id)
    if run is None:
        return
    run.total_articles = total_articles
    run.rejected_count = rejected_count
    run.status = status
    run.finished_at = datetime.now(UTC)
    await session.flush()


async def persist_article(
    session: AsyncSession, state: PipelineState
) -> Article | None:
    """Insert a published article and its image. Returns the persisted row,
    or `None` if `state.status == 'rejected'`."""
    if state.get("status") == "rejected" or state.get("final_draft") is None:
        return None
    final = state["final_draft"]
    image = state.get("image")
    verdict = state.get("editor_verdict")
    assert final is not None

    image_asset = None
    if image is not None:
        image_asset = ImageAsset(
            gcs_uri=image.get("gcs_uri"),
            public_url=image["public_url"],
            prompt=image["prompt"],
            width=image["width"] or 1024,
            height=image["height"] or 1024,
            mime_type="image/png",
            aspect_ratio=image["aspect_ratio"],
        )
        session.add(image_asset)
        await session.flush()

    publish_date = state["publish_date"]
    section = state["section"]
    taken = await _slug_taken(session, publish_date=publish_date, section=section)
    slug = disambiguate(base_slug(final["headline"]), exists=taken.__contains__)

    status = state.get("status", "published")
    db_status = "published" if status in ("published", "approved_with_concerns") else "rejected"

    article = Article(
        slug=slug,
        publish_date=publish_date,
        section=section,
        writer=state["writer"],
        headline=final["headline"],
        subheadline=final["subheadline"],
        body_html=final["body_html"],
        image_asset_id=image_asset.id if image_asset else None,
        image_alt=image["image_alt"] if image else None,
        source_id=state["source"]["id"],
        run_id=uuid.UUID(state["run_id"]) if isinstance(state["run_id"], str) else state["run_id"],
        editor_score=verdict["score"] if verdict else None,
        status=db_status,
    )
    session.add(article)
    await session.flush()
    return article


async def write_front_page_picks(
    session: AsyncSession,
    *,
    publish_date: date,
    picks: dict[str, Article],
) -> None:
    # Upsert: clear existing then re-insert. Idempotent over re-runs.
    await session.execute(
        delete(FrontPagePick).where(FrontPagePick.publish_date == publish_date)
    )
    for slot, article in picks.items():
        session.add(
            FrontPagePick(publish_date=publish_date, slot=slot, article_id=article.id)
        )
    await session.flush()
