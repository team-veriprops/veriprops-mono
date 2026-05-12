"""S39 -- notifications, notification_dispatches, notification_preferences tables.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-12 00:01:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.appodus_utils.db.models import UTCDateTime

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- notifications -------------------------------------------------
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(36), nullable=False, primary_key=True),
        sa.Column("date_created", UTCDateTime, nullable=False),
        sa.Column("date_updated", UTCDateTime, nullable=True),
        sa.Column("date_deleted", UTCDateTime, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, default=1),
        sa.Column("deleted", sa.Boolean, nullable=False, default=False),
        sa.Column("recipient_id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("entity_type", sa.String(40), nullable=True),
        sa.Column("entity_id", sa.String(36), nullable=True),
        sa.Column("read", sa.Boolean, nullable=False, default=False),
    )
    op.create_index("ix_notifications_id", "notifications", ["id"], unique=True)
    op.create_index("ix_notifications_recipient_id", "notifications", ["recipient_id"])
    op.create_index("ix_notifications_event_type", "notifications", ["event_type"])

    # -- notification_dispatches ----------------------------------------
    op.create_table(
        "notification_dispatches",
        sa.Column("id", sa.String(36), nullable=False, primary_key=True),
        sa.Column("date_created", UTCDateTime, nullable=False),
        sa.Column("date_updated", UTCDateTime, nullable=True),
        sa.Column("date_deleted", UTCDateTime, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, default=1),
        sa.Column("deleted", sa.Boolean, nullable=False, default=False),
        sa.Column("notification_id", sa.String(36), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, default="PENDING"),
        sa.Column("provider_ref", sa.String(200), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
    )
    op.create_index("ix_notification_dispatches_id", "notification_dispatches", ["id"], unique=True)
    op.create_index("ix_notification_dispatches_notif_id", "notification_dispatches", ["notification_id"])

    # -- notification_preferences ----------------------------------------
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.String(36), nullable=False, primary_key=True),
        sa.Column("date_created", UTCDateTime, nullable=False),
        sa.Column("date_updated", UTCDateTime, nullable=True),
        sa.Column("date_deleted", UTCDateTime, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, default=1),
        sa.Column("deleted", sa.Boolean, nullable=False, default=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("email_enabled", sa.Boolean, nullable=False, default=True),
        sa.Column("sms_enabled", sa.Boolean, nullable=False, default=False),
        sa.Column("push_enabled", sa.Boolean, nullable=False, default=False),
    )
    op.create_index("ix_notification_preferences_id", "notification_preferences", ["id"], unique=True)
    op.create_index("ix_notification_preferences_user_id", "notification_preferences", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_notification_preferences_user_id", table_name="notification_preferences")
    op.drop_index("ix_notification_preferences_id", table_name="notification_preferences")
    op.drop_table("notification_preferences")

    op.drop_index("ix_notification_dispatches_notif_id", table_name="notification_dispatches")
    op.drop_index("ix_notification_dispatches_id", table_name="notification_dispatches")
    op.drop_table("notification_dispatches")

    op.drop_index("ix_notifications_event_type", table_name="notifications")
    op.drop_index("ix_notifications_recipient_id", table_name="notifications")
    op.drop_index("ix_notifications_id", table_name="notifications")
    op.drop_table("notifications")
