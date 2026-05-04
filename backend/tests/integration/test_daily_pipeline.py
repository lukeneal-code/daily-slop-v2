"""End-to-end pipeline test against a real Postgres + FAKE_LLM clients.

Requires `DATABASE_URL` / `DATABASE_URL_SYNC` to point at a running Postgres with
the migrations applied. The docker-compose `db` service satisfies both.

Skipped automatically when `INTEGRATION_DB=0` to keep `pytest -m "not eval"` runnable
without docker.
"""

from __future__ import annotations

import os
import socket
import uuid
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy import select, text

from app.config import get_settings
from app.db.models import Article, FrontPagePick, SourceArticle
from app.db.session import engine, session_factory


def _db_reachable() -> bool:
    if os.environ.get("INTEGRATION_DB") == "0":
        return False
    s = socket.socket()
    s.settimeout(0.5)
    try:
        s.connect(("localhost", 5432))
        return True
    except OSError:
        return False
    finally:
        s.close()


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _db_reachable(), reason="Postgres not reachable on localhost:5432"),
]


@pytest_asyncio.fixture
async def isolated_db(monkeypatch, tmp_path):
    """Reset the public schema so every test starts clean against the running DB."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://slop:slop@localhost:5432/slop")
    monkeypatch.setenv(
        "DATABASE_URL_SYNC", "postgresql+psycopg://slop:slop@localhost:5432/slop"
    )
    monkeypatch.setenv("FAKE_LLM", "true")
    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("IMAGES_LOCAL_DIR", str(tmp_path / "images"))
    monkeypatch.setenv("IMAGES_PUBLIC_BASE_URL", "http://test/images")

    get_settings.cache_clear()
    engine.cache_clear()
    session_factory.cache_clear()

    Session = session_factory()  # noqa: N806 — SQLAlchemy convention
    async with Session() as session:
        # Truncate everything but `sections` (seeded by Alembic) and `alembic_version`.
        await session.execute(
            text(
                "TRUNCATE TABLE agent_steps, agent_runs, front_page_picks, articles, "
                "image_assets, source_articles RESTART IDENTITY CASCADE"
            )
        )
        await session.commit()

    yield Session

    get_settings.cache_clear()
    engine.cache_clear()
    session_factory.cache_clear()


@pytest_asyncio.fixture
async def seeded_sources(isolated_db):
    """Insert two source articles per section so the pipeline has candidates."""
    Session = isolated_db  # noqa: N806 — SQLAlchemy convention
    async with Session() as session:
        for section in ["politics", "business", "tech", "culture", "sport", "royals"]:
            for n in range(2):
                session.add(
                    SourceArticle(
                        external_id=f"seed:{section}:{n}",
                        outlet="BBC" if n == 0 else "Guardian",
                        title=f"{section} headline {n}",
                        description="",
                        url=f"https://example.com/{section}/{n}",
                        section=section,
                    )
                )
        await session.commit()
    return Session


@pytest.mark.asyncio
async def test_run_daily_persists_articles_and_front_page(seeded_sources, monkeypatch):
    # Patch scrape_all to return nothing so we don't depend on real RSS feeds in tests.
    from app.pipeline import daily as daily_module

    monkeypatch.setattr(daily_module, "scrape_all", lambda: [])

    result = await daily_module.run_daily(date(2026, 5, 3))

    assert result.publish_date == date(2026, 5, 3)
    assert isinstance(result.run_id, uuid.UUID)
    assert result.total_articles >= 6  # at least one per section

    Session = seeded_sources  # noqa: N806 — SQLAlchemy convention
    async with Session() as session:
        articles = (
            await session.execute(select(Article).where(Article.publish_date == date(2026, 5, 3)))
        ).scalars().all()
        assert len(articles) >= 6
        # Every article must reference an image.
        for a in articles:
            assert a.image_asset_id is not None
            assert a.editor_score is not None

        picks = (
            await session.execute(
                select(FrontPagePick).where(FrontPagePick.publish_date == date(2026, 5, 3))
            )
        ).scalars().all()
        slots = {p.slot for p in picks}
        assert "headline" in slots
        assert {"small_1", "small_2"} & slots  # at least one small picked

        # Front-page diversity: headline + small_1 should be different sections.
        slot_to_section = {}
        for p in picks:
            art = await session.get(Article, p.article_id)
            slot_to_section[p.slot] = art.section
        if "small_1" in slot_to_section:
            assert slot_to_section["small_1"] != slot_to_section["headline"]
