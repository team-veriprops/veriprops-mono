"""task commission lock — a task pays the commission its agent accepted it at (§12.1 / §20.1).

The agent's task card shows the role's fixed commission before accept, but accrual read the live
rate at release, so an admin's later change moved what the agent had agreed to.
``verification_tasks.commission_minor`` holds the rate locked at accept. It is nullable and not
backfilled: a task accepted before this revision has no lock and is paid the live rate, which is
exactly what it would have been paid without this change.

The downgrade drops the column, but refuses while an unpaid task (not yet APPROVED or CANCELLED)
holds a lock: dropping it would pay that task the live rate instead of the one its agent accepted.

Revision ID: 0009_task_commission_lock
Revises: 0008_drop_signup_drafts
Create Date: 2026-10-01 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.alembic.utils import AlembicUtils

revision: str = "0009_task_commission_lock"
down_revision: Union[str, None] = "0008_drop_signup_drafts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "verification_tasks"
_COLUMN = "commission_minor"
# Raw strings by design — migrations stay decoupled from app enums. A task in either state has
# been settled (accrued or closed unpaid), so its lock no longer decides any pay.
_SETTLED_STATES = "('APPROVED', 'CANCELLED')"


def upgrade() -> None:
    op.add_column(_TABLE, sa.Column(_COLUMN, sa.BigInteger(), nullable=True))


def downgrade() -> None:
    AlembicUtils.refuse_if_rows(
        f"SELECT count(*) FROM {_TABLE} WHERE deleted = false AND {_COLUMN} IS NOT NULL "
        f"AND state NOT IN {_SETTLED_STATES}",
        "unpaid tasks hold the commission their agents accepted",
    )
    op.drop_column(_TABLE, _COLUMN)
