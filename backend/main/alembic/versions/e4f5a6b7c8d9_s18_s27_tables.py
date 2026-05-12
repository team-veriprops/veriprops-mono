"""S18-S27 tables: admin_config, verification_notes, tasks, task_assignments, evidence_items, escalations

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-05-11 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.alembic.utils import AlembicUtils
from main.appodus_utils.db.models import UTCDateTime

revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── admin_config ──────────────────────────────────────────────
    op.create_table(
        "admin_config",
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_admin_config_id", "admin_config", ["id"], unique=True)
    op.create_index("ix_admin_config_deleted", "admin_config", ["deleted"])
    op.create_index("ix_admin_config_updated_by", "admin_config", ["updated_by"])
    op.create_unique_constraint("uq_admin_config_key", "admin_config", ["key"])

    # ── verification_notes (S18) ──────────────────────────────────
    op.create_table(
        "verification_notes",
        sa.Column("verification_id", sa.String(36), nullable=False),
        sa.Column("admin_id", sa.String(36), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("tags", sa.JSON, nullable=True),
        sa.Column("pinned", sa.Boolean, nullable=False, default=False),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_verification_notes_id", "verification_notes", ["id"], unique=True)
    op.create_index("ix_verification_notes_deleted", "verification_notes", ["deleted"])
    op.create_index("ix_verification_notes_verification_id", "verification_notes", ["verification_id"])
    op.create_index("ix_verification_notes_admin_id", "verification_notes", ["admin_id"])

    # ── tasks (S19) ───────────────────────────────────────────────
    op.create_table(
        "tasks",
        sa.Column("verification_id", sa.String(36), nullable=False),
        # role: FIELD / SURVEYOR / REGISTRY / LAWYER
        sa.Column("role", sa.String(16), nullable=False),
        # agent_id null = unclaimed/PENDING; set on accept or admin direct-assign
        sa.Column("agent_id", sa.String(36), nullable=True),
        # PENDING / ASSIGNED / ACCEPTED / IN_PROGRESS / SUBMITTED / APPROVED / REJECTED
        sa.Column("status", sa.String(16), nullable=False, default="PENDING"),
        sa.Column("pool_released_at", UTCDateTime, nullable=True),
        sa.Column("accepted_at", UTCDateTime, nullable=True),
        sa.Column("submitted_at", UTCDateTime, nullable=True),
        sa.Column("trust_score", sa.Integer, nullable=True),
        # JSON-encoded draft payload for draft-save feature
        sa.Column("draft_payload", sa.Text, nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_tasks_id", "tasks", ["id"], unique=True)
    op.create_index("ix_tasks_deleted", "tasks", ["deleted"])
    op.create_index("ix_tasks_verification_id", "tasks", ["verification_id"])
    op.create_index("ix_tasks_agent_id", "tasks", ["agent_id"])
    op.create_index("ix_tasks_status", "tasks", ["status"])
    op.create_index("ix_tasks_role", "tasks", ["role"])

    # ── task_assignments (S19) — assignment history ───────────────
    op.create_table(
        "task_assignments",
        sa.Column("task_id", sa.String(36), nullable=False),
        sa.Column("agent_id", sa.String(36), nullable=False),
        sa.Column("assigned_by", sa.String(36), nullable=True),
        sa.Column("reassigned_from_id", sa.String(36), nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_task_assignments_id", "task_assignments", ["id"], unique=True)
    op.create_index("ix_task_assignments_deleted", "task_assignments", ["deleted"])
    op.create_index("ix_task_assignments_task_id", "task_assignments", ["task_id"])
    op.create_index("ix_task_assignments_agent_id", "task_assignments", ["agent_id"])

    # ── evidence_items (S22-S25) ──────────────────────────────────
    op.create_table(
        "evidence_items",
        sa.Column("task_id", sa.String(36), nullable=False),
        sa.Column("uploader_id", sa.String(36), nullable=False),
        ## type: PHOTO / VIDEO / DOCUMENT / COORDINATE / OTHER
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("file_url", sa.Text, nullable=True),
        sa.Column("gps_lat", sa.Float, nullable=True),
        sa.Column("gps_lng", sa.Float, nullable=True),
        sa.Column("captured_at", UTCDateTime, nullable=True),
        sa.Column("metadata", sa.JSON, nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_evidence_items_id", "evidence_items", ["id"], unique=True)
    op.create_index("ix_evidence_items_deleted", "evidence_items", ["deleted"])
    op.create_index("ix_evidence_items_task_id", "evidence_items", ["task_id"])
    op.create_index("ix_evidence_items_uploader_id", "evidence_items", ["uploader_id"])

    # ── escalations (S27) ─────────────────────────────────────────
    op.create_table(
        "escalations",
        sa.Column("task_id", sa.String(36), nullable=False),
        sa.Column("reporter_id", sa.String(36), nullable=False),
        # INACCESSIBLE / SUSPICIOUS / SAFETY / CONFLICTING / OTHER
        sa.Column("category", sa.String(16), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_escalations_id", "escalations", ["id"], unique=True)
    op.create_index("ix_escalations_deleted", "escalations", ["deleted"])
    op.create_index("ix_escalations_task_id", "escalations", ["task_id"])
    op.create_index("ix_escalations_reporter_id", "escalations", ["reporter_id"])


def downgrade() -> None:
    op.drop_table("escalations")
    op.drop_table("evidence_items")
    op.drop_table("task_assignments")
    op.drop_table("tasks")
    op.drop_table("verification_notes")
    op.drop_table("admin_config")
