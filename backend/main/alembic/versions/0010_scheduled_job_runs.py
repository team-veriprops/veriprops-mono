"""scheduled_job_runs — when each scheduled job last ran, the clock every sweep runner shares.

Every deployed environment is serverless, where the in-process scheduler cannot be trusted to
fire, so a Cloudflare Cron Worker calls `POST /internal/sweeps/tick` every minute. The tick, and
the in-process scheduler on hosts that keep it, decide what is due from this table and claim a
job's row before running it, so concurrent runners run each fire once.

The rows are bookkeeping: the downgrade loses only when each sweep last ran, and the next
upgrade re-anchors every job at its first tick. Nothing to refuse.

Revision ID: 0010_scheduled_job_runs
Revises: 0009_task_commission_lock
Create Date: 2026-10-06 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.alembic.utils import AlembicUtils
from main.appodus_utils.db.models import UTCDateTime

revision: str = "0010_scheduled_job_runs"
down_revision: Union[str, None] = "0009_task_commission_lock"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "scheduled_job_runs"
_NAME_INDEX = "ix_scheduled_job_runs_name"


def _create_scheduled_job_runs() -> None:
    op.create_table(
        _TABLE,
        *AlembicUtils.base_audit_columns(),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("last_run_at", UTCDateTime, nullable=True),
    )
    op.create_index(_NAME_INDEX, _TABLE, ["name"], unique=True)


def upgrade() -> None:
    _create_scheduled_job_runs()


def downgrade() -> None:
    op.drop_index(_NAME_INDEX, table_name=_TABLE)
    op.drop_table(_TABLE)
