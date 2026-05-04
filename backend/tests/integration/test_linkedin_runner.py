"""Integration test for the LinkedIn post runner.

Seeds two articles + their FrontPagePicks, patches `social.linkedin` and the
HTTP image fetch with recorders, and asserts that:
- The runner persists a `linkedin_posts` row with the expected text.
- A second call is a no-op (idempotency on `publish_date` PK).
"""

from __future__ import annotations

import os
import socket
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy import select, text

from app.config import get_settings
from app.db.models import (
    AgentRun,
    Article,
    FrontPagePick,
    ImageAsset,
    LinkedInPost,
)
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
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://slop:slop@localhost:5432/slop")
    monkeypatch.setenv(
        "DATABASE_URL_SYNC", "postgresql+psycopg://slop:slop@localhost:5432/slop"
    )
    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("LINKEDIN_ORG_URN", "urn:li:organization:1")
    monkeypatch.setenv("SITE_URL", "https://dailyslop.co.uk")
    monkeypatch.setenv("IMAGES_LOCAL_DIR", str(tmp_path / "images"))
    monkeypatch.setenv("IMAGES_PUBLIC_BASE_URL", "http://test/images")

    get_settings.cache_clear()
    engine.cache_clear()
    session_factory.cache_clear()

    Session = session_factory()  # noqa: N806
    async with Session() as session:
        await session.execute(
            text(
                "TRUNCATE TABLE linkedin_posts, agent_steps, agent_runs, front_page_picks, "
                "articles, image_assets, source_articles RESTART IDENTITY CASCADE"
            )
        )
        await session.commit()

    yield Session

    get_settings.cache_clear()
    engine.cache_clear()
    session_factory.cache_clear()


@pytest_asyncio.fixture
async def seeded_picks(isolated_db):
    """Seed three articles + a FrontPagePick row for each."""
    Session = isolated_db  # noqa: N806
    publish_date = date(2026, 5, 4)
    import uuid as _uuid

    run_id = _uuid.uuid4()
    async with Session() as session:
        session.add(
            AgentRun(
                id=run_id,
                publish_date=publish_date,
                status="completed",
                total_articles=3,
                rejected_count=0,
            )
        )
        await session.flush()

        image = ImageAsset(
            gcs_uri="gs://test-bucket/img.png",
            public_url="http://test/images/img.png",
            prompt="x",
            width=1024,
            height=1024,
            aspect_ratio="1:1",
            mime_type="image/png",
        )
        session.add(image)
        await session.flush()

        for i, (section, headline) in enumerate(
            [
                ("politics", "FREDDIE STARR ATE MY HAMSTER"),
                ("business", "PM admits oven-ready was a metaphor"),
                ("tech", "Wetherspoons unveils AI bouncer"),
            ]
        ):
            session.add(
                Article(
                    slug=f"art-{i}",
                    publish_date=publish_date,
                    section=section,
                    writer="nigel",
                    headline=headline,
                    subheadline="…",
                    body_html="<p>x</p>",
                    image_asset_id=image.id,
                    status="published",
                    run_id=run_id,
                )
            )
        await session.flush()

        articles = (
            await session.execute(
                select(Article).where(Article.publish_date == publish_date)
            )
        ).scalars().all()
        slots = ["headline", "small_1", "small_2"]
        for slot, art in zip(slots, articles, strict=True):
            session.add(
                FrontPagePick(publish_date=publish_date, slot=slot, article_id=art.id)
            )
        await session.commit()
    return Session, publish_date


@pytest.mark.asyncio
async def test_runner_posts_and_is_idempotent(seeded_picks, monkeypatch):
    Session, publish_date = seeded_picks  # noqa: N806

    # Patch the linkedin module to record calls instead of hitting the network.
    calls = []

    async def fake_post_with_image(*, author_urn, commentary, image_bytes):
        calls.append(
            {
                "author_urn": author_urn,
                "commentary": commentary,
                "image_size": len(image_bytes),
            }
        )
        return "urn:li:share:FAKE"

    from app.social import linkedin as linkedin_module
    from app.social import runner as runner_module

    monkeypatch.setattr(
        runner_module.linkedin, "post_with_image", fake_post_with_image
    )
    # Avoid a real HTTP fetch for the image — return synthetic bytes.
    async def fake_fetch(_image):
        return b"\x89PNG synthetic"

    monkeypatch.setattr(runner_module, "_fetch_image_bytes", fake_fetch)

    result = await runner_module.post_today_to_linkedin(publish_date)
    assert result.status == "sent"
    assert result.post_urn == "urn:li:share:FAKE"
    assert len(result.article_ids) == 3

    assert len(calls) == 1
    payload = calls[0]
    assert payload["author_urn"] == "urn:li:organization:1"
    assert "FREDDIE STARR ATE MY HAMSTER" in payload["commentary"]
    assert "https://dailyslop.co.uk" in payload["commentary"]

    async with Session() as session:
        row = await session.get(LinkedInPost, publish_date)
        assert row is not None
        assert row.status == "sent"
        assert row.post_urn == "urn:li:share:FAKE"

    # Second call must be a no-op.
    result2 = await runner_module.post_today_to_linkedin(publish_date)
    assert result2.status == "already_sent"
    assert len(calls) == 1, "LinkedIn must not be called a second time"

    # Avoid an unused-import lint by referencing the module.
    _ = linkedin_module


@pytest.mark.asyncio
async def test_runner_skips_when_no_picks(isolated_db):
    publish_date = date(2026, 5, 4)
    from app.social.runner import post_today_to_linkedin

    result = await post_today_to_linkedin(publish_date)
    assert result.status == "skipped"

    Session = isolated_db  # noqa: N806
    async with Session() as session:
        row = await session.get(LinkedInPost, publish_date)
        assert row is not None
        assert row.status == "skipped"
