"""add linkedin_posts

Revision ID: 20260504_linkedin
Revises: 20260502_initial
Create Date: 2026-05-04 12:00:00 UTC
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260504_linkedin"
down_revision = "20260502_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "linkedin_posts",
        sa.Column("publish_date", sa.Date(), primary_key=True),
        sa.Column("post_urn", sa.Text(), nullable=True),
        sa.Column("post_text", sa.Text(), nullable=False),
        sa.Column(
            "image_asset_id", sa.Integer(), sa.ForeignKey("image_assets.id"), nullable=True
        ),
        sa.Column("article_ids", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("linkedin_posts")
