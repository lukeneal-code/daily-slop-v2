"""Upsert SourceItems into `source_articles`. Dedupes by `external_id`."""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SourceArticle
from app.scraping.rss import SourceItem


async def upsert_sources(
    session: AsyncSession, items: Iterable[SourceItem]
) -> tuple[list[SourceArticle], int]:
    """Insert any new items; return (rows_for_today, new_count)."""
    items_list = list(items)
    if not items_list:
        return [], 0

    external_ids = [i.external_id for i in items_list]
    existing = (
        await session.execute(
            select(SourceArticle.external_id).where(
                SourceArticle.external_id.in_(external_ids)
            )
        )
    ).scalars().all()
    seen = set(existing)
    new_rows: list[SourceArticle] = []
    for item in items_list:
        if item.external_id in seen:
            continue
        row = SourceArticle(
            external_id=item.external_id,
            outlet=item.outlet,
            title=item.title,
            description=item.description or None,
            url=item.url,
            image_url=item.image_url,
            section=item.section,
            published_at=item.published_at,
        )
        session.add(row)
        new_rows.append(row)
        seen.add(item.external_id)
    await session.flush()
    return new_rows, len(new_rows)
