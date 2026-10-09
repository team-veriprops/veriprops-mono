"""retries — a failed sweep and a failing broadcast page are retried, boundedly.

* `scheduled_job_runs.retry_at` — when a job that raised is due again: after
  `SCHEDULED_JOB_RETRY_SECONDS`, never later than its next normal run. Without it the daily
  payout batch waited a day after any failure.
* `broadcasts.fanout_failures` — consecutive failed attempts at the current fan-out page. A failed
  page rolls back whole and is retried; at `BROADCAST_FANOUT_MAX_FAILURES` the broadcast is FAILED
  rather than retried forever.

The downgrade drops both, but refuses while a broadcast is FAILED: the code it returns to has no
such status and could not read that broadcast at all.

Revision ID: 0012_retries
Revises: 0011_broadcast_fanout
Create Date: 2026-10-07 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.alembic.utils import AlembicUtils
from main.appodus_utils.db.models import UTCDateTime

revision: str = "0012_retries"
down_revision: Union[str, None] = "0011_broadcast_fanout"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("scheduled_job_runs", sa.Column("retry_at", UTCDateTime, nullable=True))
    op.add_column("broadcasts", sa.Column("fanout_failures", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    # Raw string by design — migrations stay decoupled from app enums.
    AlembicUtils.refuse_if_rows(
        "SELECT count(*) FROM broadcasts WHERE deleted = false AND status = 'FAILED'",
        "broadcasts are FAILED, a status the previous revision's code cannot read",
    )
    op.drop_column("broadcasts", "fanout_failures")
    op.drop_column("scheduled_job_runs", "retry_at")
