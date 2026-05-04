"""Read-side query helpers used by the public API."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Article, FrontPagePick, Section


async def list_sections(session: AsyncSession) -> list[Section]:
    rows = (
        await session.execute(select(Section).order_by(Section.sort_order))
    ).scalars().all()
    return list(rows)


async def latest_publish_date(session: AsyncSession) -> date | None:
    return (
        await session.execute(
            select(Article.publish_date)
            .where(Article.status == "published")
            .order_by(Article.publish_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def section_articles(
    session: AsyncSession, *, section: str, on_date: date
) -> list[Article]:
    rows = (
        await session.execute(
            select(Article)
            .where(
                Article.section == section,
                Article.publish_date == on_date,
                Article.status == "published",
            )
            .order_by(Article.created_at.desc())
        )
    ).scalars().all()
    return list(rows)


async def front_page(session: AsyncSession, *, on_date: date) -> list[Article]:
    rows = (
        await session.execute(
            select(Article, FrontPagePick.slot)
            .join(FrontPagePick, FrontPagePick.article_id == Article.id)
            .where(FrontPagePick.publish_date == on_date)
        )
    ).all()
    out: list[Article] = []
    for article, slot in rows:
        # Attach slot as a transient attribute for the API serialiser to pick up.
        article.__dict__["slot"] = slot
        out.append(article)
    return out


async def article_by_slug(session: AsyncSession, *, slug: str) -> Article | None:
    return (
        await session.execute(
            select(Article).where(Article.slug == slug, Article.status == "published")
        )
    ).scalar_one_or_none()


async def published_dates(session: AsyncSession) -> list[date]:
    rows = (
        await session.execute(
            select(Article.publish_date)
            .where(Article.status == "published")
            .group_by(Article.publish_date)
            .order_by(Article.publish_date.desc())
        )
    ).scalars().all()
    return list(rows)
