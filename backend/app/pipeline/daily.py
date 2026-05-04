"""End-to-end daily generation pipeline.

Runs once per day (Cloud Scheduler at 06:00 Europe/London in prod, or via the
`/admin/generate` endpoint for ad-hoc triggers). Stages:

1. **Scrape** — pull each section's RSS into `source_articles` (dedupe by external_id).
2. **Generate** — for each section, pick 3 candidates, route to a writer, run the graph
   per candidate concurrently. Persist each result.
3. **Front-page** — select top-3 across sections, write `front_page_picks`.
4. **Bookkeeping** — close the `agent_runs` row with totals.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.front_page import select_top3
from app.agents.graph import build_graph, make_initial_state
from app.agents.router import choose_writer
from app.agents.state import PipelineState, SourceRef
from app.db.models import Article, Section, SourceArticle
from app.db.session import session_factory
from app.llm.factory import build_editor, build_image, build_writers
from app.pipeline.persist import (
    finish_run,
    persist_article,
    upsert_run,
    write_front_page_picks,
)
from app.scraping.persist import upsert_sources
from app.scraping.rss import scrape_all
from app.scraping.select import select_candidates

log = logging.getLogger(__name__)


@dataclass
class DailyResult:
    run_id: uuid.UUID
    publish_date: date
    total_articles: int
    rejected_count: int
    section_counts: dict[str, int]


async def _candidates_for(
    session: AsyncSession, *, section: str, k: int = 3
) -> list[SourceArticle]:
    rows = (
        await session.execute(
            select(SourceArticle).where(
                SourceArticle.section == section,
                SourceArticle.used.is_(False),
                SourceArticle.fetch_failed.is_(False),
            )
        )
    ).scalars().all()
    return select_candidates(rows, k=k)


def _to_source_ref(row: SourceArticle) -> SourceRef:
    return SourceRef(
        id=row.id,
        external_id=row.external_id,
        outlet=row.outlet,
        title=row.title,
        description=row.description or "",
        body_text=row.body_text or "",
        url=row.url,
        section=row.section,  # type: ignore[typeddict-item]
    )


async def _generate_one(
    *,
    run_id: uuid.UUID,
    publish_date: date,
    candidate: SourceArticle,
    graph: Any,
    steve_quota: float,
) -> PipelineState:
    source = _to_source_ref(candidate)
    writer = choose_writer(source, steve_quota=steve_quota)
    state = make_initial_state(
        run_id=str(run_id),
        publish_date=publish_date,
        source=source,
        writer=writer,
    )
    result: PipelineState = await graph.ainvoke(state)
    return result


async def run_daily(
    publish_date: date,
    *,
    steve_quota: float = 0.25,
    sections: Iterable[str] | None = None,
) -> DailyResult:
    run_id = uuid.uuid4()
    log.info("daily run starting run_id=%s date=%s", run_id, publish_date)

    writers = build_writers()
    editor = build_editor()
    image_client = build_image()
    graph = build_graph(writers=writers, editor=editor, image_client=image_client)

    Session = session_factory()  # noqa: N806 — SQLAlchemy convention

    # Scrape phase (one transaction).
    async with Session() as session:
        items = scrape_all()
        log.info("scraped %d source items", len(items))
        await upsert_sources(session, items)
        await upsert_run(session, run_id=run_id, publish_date=publish_date)
        await session.commit()

    # Section list (default: all enabled sections).
    async with Session() as session:
        if sections is None:
            section_slugs = (
                await session.execute(select(Section.slug).order_by(Section.sort_order))
            ).scalars().all()
        else:
            section_slugs = list(sections)

    # Generate per section. Sections sequential, candidates within a section concurrent.
    persisted: list[Article] = []
    rejected = 0
    section_counts: dict[str, int] = {}

    for section in section_slugs:
        async with Session() as session:
            candidates = await _candidates_for(session, section=section, k=3)
        if not candidates:
            log.info("no candidates for section=%s", section)
            section_counts[section] = 0
            continue

        outputs = await asyncio.gather(
            *(
                _generate_one(
                    run_id=run_id,
                    publish_date=publish_date,
                    candidate=c,
                    graph=graph,
                    steve_quota=steve_quota,
                )
                for c in candidates
            )
        )

        async with Session() as session:
            for state, candidate in zip(outputs, candidates, strict=True):
                if state.get("status") == "rejected":
                    rejected += 1
                    continue
                article = await persist_article(session, state)
                if article is not None:
                    persisted.append(article)
                # Mark source used regardless — failures don't get retried in the same day.
                src = await session.get(SourceArticle, candidate.id)
                if src is not None:
                    src.used = True
            await session.commit()
        section_counts[section] = len([s for s in outputs if s.get("status") != "rejected"])

    # Front-page selection.
    async with Session() as session:
        rows = (
            await session.execute(
                select(Article).where(
                    Article.publish_date == publish_date,
                    Article.status == "published",
                )
            )
        ).scalars().all()
        picks = select_top3(rows)
        await write_front_page_picks(session, publish_date=publish_date, picks=picks)
        await finish_run(
            session,
            run_id=run_id,
            total_articles=len(persisted),
            rejected_count=rejected,
            status="completed",
        )
        await session.commit()

    log.info(
        "daily run done run_id=%s persisted=%d rejected=%d picks=%s",
        run_id,
        len(persisted),
        rejected,
        list(picks.keys()) if picks else [],
    )
    return DailyResult(
        run_id=run_id,
        publish_date=publish_date,
        total_articles=len(persisted),
        rejected_count=rejected,
        section_counts=section_counts,
    )
