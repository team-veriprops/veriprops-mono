"""broadcast fan-out — a broadcast reaches its audience page by page, from a cursor.

Sending a broadcast used to resolve every recipient and send every email inside one request,
which on a serverless function times out long before a large audience is reached. A broadcast
now moves to SENDING and is fanned out in keyset pages by the sweep tick:

* `broadcasts.fanout_cursor` — the last user id a page sent to; the next page starts after it.
* `broadcasts.recipients_enqueued` — recipients reached so far (0 for every existing broadcast,
  which were all sent the old way or never sent).

The downgrade drops both, but refuses while a broadcast is SENDING: without its cursor it could
never be resumed, and the code it would return to has no SENDING state to finish it.

Revision ID: 0011_broadcast_fanout
Revises: 0010_scheduled_job_runs
Create Date: 2026-10-06 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.alembic.utils import AlembicUtils

revision: str = "0011_broadcast_fanout"
down_revision: Union[str, None] = "0010_scheduled_job_runs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "broadcasts"


def upgrade() -> None:
    op.add_column(_TABLE, sa.Column("fanout_cursor", sa.String(length=36), nullable=True))
    op.add_column(_TABLE, sa.Column("recipients_enqueued", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    # Raw string by design — migrations stay decoupled from app enums.
    AlembicUtils.refuse_if_rows(
        f"SELECT count(*) FROM {_TABLE} WHERE deleted = false AND status = 'SENDING'",
        "broadcasts are mid-send and would lose the cursor they resume from",
    )
    op.drop_column(_TABLE, "recipients_enqueued")
    op.drop_column(_TABLE, "fanout_cursor")
