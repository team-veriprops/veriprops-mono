"""S35/S36 — report_views (acknowledgement) and report_versions (PDF versioning).

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-11 00:00:03.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.appodus_utils.db.models import UTCDateTime

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── report_views (S35 — first-view acknowledgement) ─────────────────────
    op.create_table(
        "report_views",
        sa.Column("id", sa.String(36), nullable=False, primary_key=True),
        sa.Column("date_created", UTCDateTime, nullable=False),
        sa.Column("date_updated", UTCDateTime, nullable=True),
        sa.Column("date_deleted", UTCDateTime, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, default=1),
        sa.Column("deleted", sa.Boolean, nullable=False, default=False),
        sa.Column("vid", sa.String(24), nullable=False),
        sa.Column("customer_id", sa.String(36), nullable=False),
        sa.Column("acknowledged_at", UTCDateTime, nullable=False),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("report_version", sa.String(16), nullable=True),
    )
    op.create_index("ix_report_views_id", "report_views", ["id"], unique=True)
    op.create_index("ix_report_views_vid", "report_views", ["vid"])
    op.create_index("ix_report_views_customer_id", "report_views", ["customer_id"])

    # ── report_versions (S36 — PDF versioning) ──────────────────────────────
    op.create_table(
        "report_versions",
        sa.Column("id", sa.String(36), nullable=False, primary_key=True),
        sa.Column("date_created", UTCDateTime, nullable=False),
        sa.Column("date_updated", UTCDateTime, nullable=True),
        sa.Column("date_deleted", UTCDateTime, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, default=1),
        sa.Column("deleted", sa.Boolean, nullable=False, default=False),
        sa.Column("vid", sa.String(24), nullable=False),
        sa.Column("version_string", sa.String(16), nullable=False),
        sa.Column("pdf_s3_key", sa.String(512), nullable=True),
        sa.Column("is_superseded", sa.Boolean, nullable=False, default=False),
        sa.Column("created_at", UTCDateTime, nullable=False),
        sa.Column("created_by", sa.String(36), nullable=True),
    )
    op.create_index("ix_report_versions_id", "report_versions", ["id"], unique=True)
    op.create_index("ix_report_versions_vid", "report_versions", ["vid"])


def downgrade() -> None:
    op.drop_index("ix_report_versions_vid", table_name="report_versions")
    op.drop_index("ix_report_versions_id", table_name="report_versions")
    op.drop_table("report_versions")
    op.drop_index("ix_report_views_customer_id", table_name="report_views")
    op.drop_index("ix_report_views_vid", table_name="report_views")
    op.drop_index("ix_report_views_id", table_name="report_views")
    op.drop_table("report_views")
