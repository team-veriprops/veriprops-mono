"""sla_breach_marker — the SLA-breach sweep claims each verification before it notifies.

The sweep used to skip a verification when an SLA-breach notification already existed. Two
runs landing together (the scheduled job and the admin sweep endpoint) both found none and
both notified, and a notification deleted later let the next run notify again. It now stamps
`sla_breach_notified_at` in one conditional update before publishing, so exactly one run wins.

Verifications already announced are marked from their earliest SLA-breach notification, so the
switch-over sends nobody a second "taking longer than planned" message. Notifications reference
a verification by its hex id.

Revision ID: 0019_sla_breach_marker
Revises: 0018_concurrency_constraints
Create Date: 2026-09-25 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.appodus_utils.db.models import UTCDateTime

revision: str = "0019_sla_breach_marker"
down_revision: Union[str, None] = "0018_concurrency_constraints"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("verifications", sa.Column("sla_breach_notified_at", UTCDateTime, nullable=True))
    op.execute(
        """
        UPDATE verifications
        SET sla_breach_notified_at = announced.first_at
        FROM (
            SELECT event_ref, min(date_created) AS first_at
            FROM notifications
            WHERE type = 'SLA_BREACHED' AND event_ref IS NOT NULL
            GROUP BY event_ref
        ) AS announced
        WHERE replace(verifications.id::text, '-', '') = announced.event_ref
        """
    )


def downgrade() -> None:
    op.drop_column("verifications", "sla_breach_notified_at")
