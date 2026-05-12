"""S49-S50 -- agent_quality_scores table; availability_status and max_travel_km
columns on agent_applications.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-12 08:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.alembic.utils import AlembicUtils

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- agent_quality_scores ------------------------------------------
    op.create_table(
        "agent_quality_scores",
        sa.Column("task_id", sa.String(36), nullable=False),
        sa.Column("agent_id", sa.String(36), nullable=False),
        sa.Column("score", sa.SmallInteger, nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("reviewed_by_admin_id", sa.String(36), nullable=False),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_agent_quality_scores_id", "agent_quality_scores", ["id"], unique=True)
    op.create_index("ix_agent_quality_scores_task_id", "agent_quality_scores", ["task_id"], unique=True)
    op.create_index("ix_agent_quality_scores_agent_id", "agent_quality_scores", ["agent_id"])

    # -- agent_applications: availability + travel ---------------------
    op.add_column(
        "agent_applications",
        sa.Column("availability_status", sa.String(20), nullable=False, server_default="AVAILABLE"),
    )
    op.add_column(
        "agent_applications",
        sa.Column("max_travel_km", sa.Integer, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_applications", "max_travel_km")
    op.drop_column("agent_applications", "availability_status")
    for idx in [
        "ix_agent_quality_scores_agent_id",
        "ix_agent_quality_scores_task_id",
        "ix_agent_quality_scores_id",
    ]:
        op.drop_index(idx, table_name="agent_quality_scores")
    op.drop_table("agent_quality_scores")
