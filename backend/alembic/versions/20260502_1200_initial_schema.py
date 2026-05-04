"""initial schema

Revision ID: 20260502_initial
Revises:
Create Date: 2026-05-02 12:00:00 UTC
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260502_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sections",
        sa.Column("slug", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "source_articles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("external_id", sa.String(512), nullable=False, unique=True),
        sa.Column("outlet", sa.String(64), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column(
            "section", sa.String(32), sa.ForeignKey("sections.slug"), nullable=False
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "scraped_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "fetch_failed", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.create_index("ix_source_articles_section", "source_articles", ["section"])
    op.create_index("ix_source_articles_used", "source_articles", ["used"])

    op.create_table(
        "image_assets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("gcs_uri", sa.Text(), nullable=True),
        sa.Column("public_url", sa.Text(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column(
            "mime_type", sa.String(64), nullable=False, server_default="image/png"
        ),
        sa.Column("aspect_ratio", sa.String(16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("publish_date", sa.Date(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status", sa.String(32), nullable=False, server_default="running"
        ),
        sa.Column("langfuse_trace_id", sa.String(128), nullable=True),
        sa.Column("total_articles", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_agent_runs_publish_date", "agent_runs", ["publish_date"])

    op.create_table(
        "articles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("publish_date", sa.Date(), nullable=False),
        sa.Column(
            "section", sa.String(32), sa.ForeignKey("sections.slug"), nullable=False
        ),
        sa.Column("writer", sa.String(16), nullable=False),
        sa.Column("headline", sa.Text(), nullable=False),
        sa.Column("subheadline", sa.Text(), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=False),
        sa.Column(
            "image_asset_id", sa.Integer(), sa.ForeignKey("image_assets.id"), nullable=True
        ),
        sa.Column("image_alt", sa.Text(), nullable=True),
        sa.Column(
            "source_id", sa.Integer(), sa.ForeignKey("source_articles.id"), nullable=True
        ),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_runs.id"),
            nullable=True,
        ),
        sa.Column("editor_score", sa.Numeric(4, 2), nullable=True),
        sa.Column(
            "status", sa.String(16), nullable=False, server_default="published"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("publish_date", "section", "slug"),
    )
    op.create_index("ix_articles_publish_date", "articles", ["publish_date"])
    op.create_index("ix_articles_section", "articles", ["section"])
    op.create_index("ix_articles_slug", "articles", ["slug"])

    op.create_table(
        "front_page_picks",
        sa.Column("publish_date", sa.Date(), primary_key=True),
        sa.Column("slot", sa.String(16), primary_key=True),
        sa.Column(
            "article_id", sa.Integer(), sa.ForeignKey("articles.id"), nullable=False
        ),
    )

    op.create_table(
        "agent_steps",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_runs.id"),
            nullable=False,
        ),
        sa.Column(
            "article_id", sa.Integer(), sa.ForeignKey("articles.id"), nullable=True
        ),
        sa.Column("node", sa.String(64), nullable=False),
        sa.Column("input_jsonb", postgresql.JSONB, nullable=True),
        sa.Column("output_jsonb", postgresql.JSONB, nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=True),
    )
    op.create_index("ix_agent_steps_run_id", "agent_steps", ["run_id"])
    op.create_index("ix_agent_steps_article_id", "agent_steps", ["article_id"])

    # Seed sections.
    op.bulk_insert(
        sa.table(
            "sections",
            sa.column("slug", sa.String),
            sa.column("name", sa.String),
            sa.column("description", sa.Text),
            sa.column("sort_order", sa.Integer),
        ),
        [
            {"slug": "politics", "name": "Politics",
             "description": "Westminster, elections, party drama.", "sort_order": 1},
            {"slug": "business", "name": "Business",
             "description": "Markets, CEOs, and the slow violence of a quarterly call.",
             "sort_order": 2},
            {"slug": "tech", "name": "Tech",
             "description": "AI hype, Silicon Valley, startups.", "sort_order": 3},
            {"slug": "culture", "name": "Culture",
             "description": "Arts, media, celebrity, social trends.", "sort_order": 4},
            {"slug": "sport", "name": "Sport",
             "description": "Football, Olympics, sporting absurdity.", "sort_order": 5},
            {"slug": "royals", "name": "Royals",
             "description": "Palace gossip, ceremony, monarchy.", "sort_order": 6},
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_steps_article_id", table_name="agent_steps")
    op.drop_index("ix_agent_steps_run_id", table_name="agent_steps")
    op.drop_table("agent_steps")
    op.drop_table("front_page_picks")
    op.drop_index("ix_articles_slug", table_name="articles")
    op.drop_index("ix_articles_section", table_name="articles")
    op.drop_index("ix_articles_publish_date", table_name="articles")
    op.drop_table("articles")
    op.drop_index("ix_agent_runs_publish_date", table_name="agent_runs")
    op.drop_table("agent_runs")
    op.drop_table("image_assets")
    op.drop_index("ix_source_articles_used", table_name="source_articles")
    op.drop_index("ix_source_articles_section", table_name="source_articles")
    op.drop_table("source_articles")
    op.drop_table("sections")
