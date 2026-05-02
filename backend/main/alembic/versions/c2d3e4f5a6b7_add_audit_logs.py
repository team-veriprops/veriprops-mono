"""add_audit_logs: R0.10 — AuditLog entity for every state-machine transition.

Every service that mutates state schedules an AuditLog write via
AuditLogService.schedule(). The @transactional decorator drains the queue
atomically after flush.

Revision ID: c2d3e4f5a6b7
Revises: b1f2c3d4e5f6
Create Date: 2026-05-02 16:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, None] = "b1f2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id",            sa.String(36),                     nullable=False),
        sa.Column("date_created",  sa.DateTime(timezone=True),        nullable=True),
        sa.Column("created_by",    sa.String(36),                     nullable=True),
        sa.Column("date_updated",  sa.DateTime(timezone=True),        nullable=True),
        sa.Column("updated_by",    sa.String(36),                     nullable=True),
        sa.Column("deleted",       sa.Boolean(),                      nullable=True),
        sa.Column("date_deleted",  sa.DateTime(timezone=True),        nullable=True),
        sa.Column("deleted_by",    sa.String(36),                     nullable=True),
        sa.Column("version",       sa.Integer(),                      nullable=True),
        sa.Column("actor_id",      sa.String(36),                     nullable=True),
        sa.Column("action",        sa.String(64),                     nullable=False),
        sa.Column("resource_type", sa.String(64),                     nullable=False),
        sa.Column("resource_id",   sa.String(36),                     nullable=False),
        sa.Column("from_state",    sa.String(32),                     nullable=True),
        sa.Column("to_state",      sa.String(32),                     nullable=True),
        sa.Column("meta",          sa.JSON(),                         nullable=True),
        sa.Column("ip_address",    sa.String(64),                     nullable=True),
        sa.Column("occurred_at",   sa.DateTime(timezone=True),        nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    # Per-column indexes
    op.create_index("ix_audit_logs_id",            "audit_logs", ["id"])
    op.create_index("ix_audit_logs_deleted",        "audit_logs", ["deleted"])
    op.create_index("ix_audit_logs_actor_id",       "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_action",         "audit_logs", ["action"])
    op.create_index("ix_audit_logs_resource_type",  "audit_logs", ["resource_type"])
    op.create_index("ix_audit_logs_resource_id",    "audit_logs", ["resource_id"])
    op.create_index("ix_audit_logs_occurred_at",    "audit_logs", ["occurred_at"])
    # Composite index for per-resource audit-export query (R19.1)
    op.create_index("ix_audit_logs_resource",       "audit_logs", ["resource_type", "resource_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_resource",      table_name="audit_logs")
    op.drop_index("ix_audit_logs_occurred_at",   table_name="audit_logs")
    op.drop_index("ix_audit_logs_resource_id",   table_name="audit_logs")
    op.drop_index("ix_audit_logs_resource_type", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action",        table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_id",      table_name="audit_logs")
    op.drop_index("ix_audit_logs_deleted",       table_name="audit_logs")
    op.drop_index("ix_audit_logs_id",            table_name="audit_logs")
    op.drop_table("audit_logs")
