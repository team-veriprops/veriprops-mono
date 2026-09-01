"""whatsapp_bot_sessions — per-conversation bot state, plus the human-coverage config.

Additive, per decision D49 (`0001_initial_schema` is frozen).

One row per WhatsApp number: where the conversation is, whether a human has taken it over,
and how many turns in a row the bot has failed to understand (§7.3.3, §7.6). No case data
lives here — the bot reads that through the same services the dashboard uses, so there is
never a second copy of a verification's state to disagree with the first.

The four `system_config` rows are Decision G's staffed hours (D68). They are seeded here
as well as in `0001` because `0001` only runs on a fresh database: an environment already
migrated past it would otherwise have a bot promising a response window it had no value
for.

Revision ID: 0006_whatsapp_bot_sessions
Revises: 0005_whatsapp_templates
Create Date: 2026-09-01 00:00:00.000000
"""
import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.alembic.utils import AlembicUtils
from main.appodus_utils import Utils
from main.appodus_utils.db.models import UTCDateTime, JSONB_VARIANT

# revision identifiers, used by Alembic.
revision: str = "0006_whatsapp_bot_sessions"
down_revision: Union[str, None] = "0005_whatsapp_templates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Raw strings/values by design — migrations stay decoupled from app enums.
_MODE_BOT = "BOT"

# Decision G's coverage window, in West Africa Time. Duplicated from `CONFIG_DEFAULTS`
# rather than imported: a migration that imported app constants would rewrite history
# whenever a default changed.
_SUPPORT_CONFIG_ROWS = [
    (
        "support_hours_start",
        8,
        "First staffed hour for human support, 24-hour clock, West Africa Time.",
    ),
    (
        "support_hours_end",
        20,
        "Last staffed hour on a weekday, 24-hour clock, West Africa Time.",
    ),
    (
        "support_saturday_end",
        13,
        "Last staffed hour on Saturday (there is no Sunday cover).",
    ),
    (
        "offline_response_hours",
        12,
        "Response time the bot promises when it escalates outside staffed hours.",
    ),
]


def _create_whatsapp_bot_sessions() -> None:
    op.create_table(
        "whatsapp_bot_sessions",
        # E.164 with the leading '+', matching `whatsapp_links.phone_e164` and the
        # conversation's `external_ref`.
        sa.Column("phone_e164", sa.String(length=32), nullable=False),
        sa.Column("mode", sa.String(length=10), nullable=False, server_default=_MODE_BOT),
        sa.Column("mode_changed_at", UTCDateTime, nullable=True),
        sa.Column("current_flow", sa.String(length=24), nullable=True),
        sa.Column("step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("context", JSONB_VARIANT, nullable=True),
        sa.Column("last_inbound_at", UTCDateTime, nullable=True),
        sa.Column("welcomed_at", UTCDateTime, nullable=True),
        sa.Column("unmatched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_escalation_reason", sa.String(length=32), nullable=True),
        sa.Column("last_escalated_at", UTCDateTime, nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index(
        "ix_whatsapp_bot_sessions_id", "whatsapp_bot_sessions", ["id"], unique=True
    )
    # One session per number: two rows would mean two half-remembered conversations
    # with one person, and the sticky-HUMAN rule would hold on only one of them.
    op.create_unique_constraint(
        "uq_whatsapp_bot_sessions_phone_e164", "whatsapp_bot_sessions", ["phone_e164"]
    )


def _seed_support_hours_config() -> None:
    """Insert each coverage key at its default; never overwrites an admin's edit."""
    conn = op.get_bind()
    for key, value, description in _SUPPORT_CONFIG_ROWS:
        existing = conn.execute(
            sa.text("SELECT 1 FROM system_config WHERE key = :key LIMIT 1"), {"key": key}
        ).first()
        if existing:
            continue
        conn.execute(
            sa.text(
                "INSERT INTO system_config "
                "(id, key, value_json, description, date_created, deleted, version) "
                "VALUES (:id, :key, :value_json, :description, :now, FALSE, 1)"
            ),
            {
                "id": Utils.generate_uuid(),
                "key": key,
                "value_json": json.dumps(value),
                "description": description,
                "now": Utils.datetime_now(),
            },
        )


def upgrade() -> None:
    _create_whatsapp_bot_sessions()
    _seed_support_hours_config()


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM system_config WHERE key = ANY(:keys)"),
        {"keys": [key for key, _value, _description in _SUPPORT_CONFIG_ROWS]},
    )
    op.drop_table("whatsapp_bot_sessions")
