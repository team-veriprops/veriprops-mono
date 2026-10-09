"""d97_config_rows — every database holds the two config rows D97 introduced.

`0001` seeds `system_config` from the app's live defaults, so a fresh build has rows for
`commission_min_margin_pct` and `remote_job_bonus_ngn_kobo`. A database that ran an earlier `0001`
and then `0002` (D97) has neither: its readers fall back to the same defaults, so it behaved the
same, but the two kinds of database differed. This inserts each row only where its key is absent,
so a fresh build and any admin edit are untouched.

The downgrade removes nothing. It cannot tell a row inserted here from one `0001` seeded or an
admin saved, and a row at its default changes nothing the previous revision reads.

Revision ID: 0013_d97_config_rows
Revises: 0012_retries
Create Date: 2026-10-08 00:00:00.000000
"""
import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.appodus_utils import Utils

revision: str = "0013_d97_config_rows"
down_revision: Union[str, None] = "0012_retries"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Raw keys and defaults by design — migrations stay decoupled from app enums. The description is
# left to the code (`ConfigService.list_all` shows the code-owned copy over a stored one).
ROWS = [
    {"key": "commission_min_margin_pct", "value_json": json.dumps(30)},
    {"key": "remote_job_bonus_ngn_kobo", "value_json": json.dumps(0)},
]


def upgrade() -> None:
    # The same check-then-insert as 0001's `_seed_system_config`: any row for the key, live or
    # deleted, means it was decided already.
    conn = op.get_bind()
    for row in ROWS:
        if conn.execute(
            sa.text("SELECT 1 FROM system_config WHERE key = :key LIMIT 1"), {"key": row["key"]},
        ).first():
            continue
        conn.execute(
            sa.text(
                "INSERT INTO system_config (id, key, value_json, date_created, deleted, version) "
                "VALUES (:id, :key, :value_json, :now, FALSE, 1)"
            ),
            {"id": Utils.generate_uuid(), "now": Utils.datetime_now(), **row},
        )


def downgrade() -> None:
    # Nothing to undo: see the module docstring.
    pass
