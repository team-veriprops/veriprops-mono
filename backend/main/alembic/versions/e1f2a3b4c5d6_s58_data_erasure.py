"""S58 -- data_erasure_requests table.

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-05-14 00:03:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.alembic.utils import AlembicUtils
from main.appodus_utils.db.models import UTCDateTime

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "data_erasure_requests",
        sa.Column("user_id", sa.String(36), nullable=False, index=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("requested_at", UTCDateTime, nullable=False),
        sa.Column("reviewed_by", sa.String(36), nullable=True),
        sa.Column("reviewed_at", UTCDateTime, nullable=True),
        sa.Column("executed_at", UTCDateTime, nullable=True),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index(
        "ix_data_erasure_requests_user_status",
        "data_erasure_requests",
        ["user_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_data_erasure_requests_user_status", table_name="data_erasure_requests")
    op.drop_table("data_erasure_requests")
