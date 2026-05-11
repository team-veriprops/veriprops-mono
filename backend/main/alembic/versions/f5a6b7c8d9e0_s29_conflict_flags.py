"""S29 — conflict_flags table for automated conflict detection.

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-05-11 00:00:01.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.appodus_utils.db.models import UTCDateTime

revision: str = "f5a6b7c8d9e0"
down_revision: Union[str, None] = "e4f5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conflict_flags",
        sa.Column("id", sa.String(36), nullable=False, primary_key=True),
        sa.Column("date_created", UTCDateTime, nullable=False),
        sa.Column("date_updated", UTCDateTime, nullable=True),
        sa.Column("date_deleted", UTCDateTime, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, default=1),
        sa.Column("deleted", sa.Boolean, nullable=False, default=False),
        sa.Column("verification_id", sa.String(36), nullable=False),
        sa.Column("rule_id", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("resolution_note", sa.Text, nullable=True),
        sa.Column("resolved_by", sa.String(36), nullable=True),
        sa.Column("resolved_at", UTCDateTime, nullable=True),
    )
    op.create_index("ix_conflict_flags_id", "conflict_flags", ["id"], unique=True)
    op.create_index("ix_conflict_flags_verification_id", "conflict_flags", ["verification_id"])
    op.create_index("ix_conflict_flags_status", "conflict_flags", ["status"])
    op.create_index(
        "ix_conflict_flags_vid_status",
        "conflict_flags",
        ["verification_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_conflict_flags_vid_status", table_name="conflict_flags")
    op.drop_index("ix_conflict_flags_status", table_name="conflict_flags")
    op.drop_index("ix_conflict_flags_verification_id", table_name="conflict_flags")
    op.drop_index("ix_conflict_flags_id", table_name="conflict_flags")
    op.drop_table("conflict_flags")
