"""S37-S38 -- message_threads, thread_messages, fraud_flags tables.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-12 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.alembic.utils import AlembicUtils
from main.appodus_utils.db.models import UTCDateTime

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- message_threads -------------------------------------------
    op.create_table(
        "message_threads",
        sa.Column("thread_type", sa.String(20), nullable=False),
        sa.Column("verification_id", sa.String(36), nullable=False),
        sa.Column("task_id", sa.String(36), nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_threads_id", "message_threads", ["id"], unique=True)
    op.create_index("ix_threads_thread_type", "message_threads", ["thread_type"])
    op.create_index("ix_threads_verification_id", "message_threads", ["verification_id"])
    op.create_index("ix_threads_task_id", "message_threads", ["task_id"])
    op.create_index(
        "ix_threads_verification_type",
        "message_threads",
        ["verification_id", "thread_type"],
    )

    # -- thread_messages -------------------------------------------
    op.create_table(
        "thread_messages",
        sa.Column("thread_id", sa.String(36), nullable=False),
        sa.Column("sender_id", sa.String(36), nullable=True),
        sa.Column("sender_role", sa.String(16), nullable=False),
        sa.Column("message_type", sa.String(16), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("attachment_key", sa.String(512), nullable=True),
        sa.Column("is_held", sa.Boolean, nullable=False, default=False),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_thread_messages_id", "thread_messages", ["id"], unique=True)
    op.create_index("ix_thread_messages_thread_id", "thread_messages", ["thread_id"])

    # -- fraud_flags -----------------------------------------------
    op.create_table(
        "fraud_flags",
        sa.Column("message_id", sa.String(36), nullable=False),
        sa.Column("message_body", sa.Text, nullable=False),
        sa.Column("matched_patterns", sa.Text, nullable=False),
        sa.Column("reviewed", sa.Boolean, nullable=False, default=False),
        sa.Column("review_decision", sa.String(16), nullable=True),
        sa.Column("reviewer_id", sa.String(36), nullable=True),
        sa.Column("reviewed_at", UTCDateTime, nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_fraud_flags_id", "fraud_flags", ["id"], unique=True)
    op.create_index("ix_fraud_flags_message_id", "fraud_flags", ["message_id"])


def downgrade() -> None:
    op.drop_index("ix_fraud_flags_message_id", table_name="fraud_flags")
    op.drop_index("ix_fraud_flags_id", table_name="fraud_flags")
    op.drop_table("fraud_flags")

    op.drop_index("ix_thread_messages_thread_id", table_name="thread_messages")
    op.drop_index("ix_thread_messages_id", table_name="thread_messages")
    op.drop_table("thread_messages")

    op.drop_index("ix_threads_verification_type", table_name="message_threads")
    op.drop_index("ix_threads_task_id", table_name="message_threads")
    op.drop_index("ix_threads_verification_id", table_name="message_threads")
    op.drop_index("ix_threads_thread_type", table_name="message_threads")
    op.drop_index("ix_threads_id", table_name="message_threads")
    op.drop_table("message_threads")
