"""Channel analytics — the §7.10 fact table, page-code attribution, and Meta number health.

Additive, per decision D49 (`0001_initial_schema` is frozen).

Three things, all serving PRD §7.10 (WA-43):

* **``whatsapp_channel_events``** (D80) — an append-only fact table. Four of §7.10's seven
  metrics are *rates over a window*, and none of them could be answered by what the channel
  already stored: `whatsapp_bot_sessions` holds one mutated row per number, so the previous
  escalation reason is gone the moment a new one is recorded, and `current_flow` is cleared
  when a flow ends, so a finished intake is indistinguishable from one that never started.
  `audit_logs` was the other candidate and is the wrong home: it is the legal transition
  ledger the §19.3 pack exports.
* **``whatsapp_inbound_messages.page_code``** (D85) — the widget's `[ref: …]` marker,
  lifted out of the message text at normalization. Plus an index on `(kind, received_at)`,
  because the voice-note count is now windowed and was otherwise a sequential scan.
* **``whatsapp_number_health``** (D81) — Meta's quality rating for our sending number,
  cached in the same posture as the §7.7 template registry: their verdict, our timestamp,
  and nothing in the send path ever reads it.

The `system_config` row is seeded here as well as in `0001` for the reason `0006` gives:
`0001` only runs on a fresh database, and an already-migrated environment would otherwise
have the analytics endpoint asking for a window size that does not exist.

Revision ID: 0010_whatsapp_channel_analytics
Revises: 0009_case_delegates
Create Date: 2026-09-03 00:00:00.000000
"""
import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.alembic.utils import AlembicUtils
from main.appodus_utils import Utils
from main.appodus_utils.db.models import JSONB_VARIANT, UTCDateTime

# revision identifiers, used by Alembic.
revision: str = "0010_whatsapp_channel_analytics"
down_revision: Union[str, None] = "0009_case_delegates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CONFIG_ROWS = [
    (
        "channel_analytics_window_days",
        30,
        "Trailing days covered by the WhatsApp channel analytics (PRD §7.10). Four of the "
        "seven metrics are rates, and a rate with no period cannot show whether a change "
        "worked.",
    ),
]


def _create_whatsapp_channel_events() -> None:
    op.create_table(
        "whatsapp_channel_events",
        # When the thing happened, which is not always when the row was written: a fact
        # recorded from an event subscriber lags its cause. Every metric windows on this.
        sa.Column("occurred_at", UTCDateTime, nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("phone_e164", sa.String(length=32), nullable=True),
        # Free text, not an enum: the codes name frontend routes the backend does not
        # model, and the widget derives one for any new page without a table edit.
        sa.Column("page_code", sa.String(length=40), nullable=True),
        sa.Column("reason", sa.String(length=32), nullable=True),
        sa.Column("verification_id", sa.String(length=36), nullable=True),
        sa.Column("customer_id", sa.String(length=36), nullable=True),
        sa.Column("detail", JSONB_VARIANT, nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index(
        "ix_whatsapp_channel_events_id", "whatsapp_channel_events", ["id"], unique=True
    )
    # Every §7.10 metric is "rows of this type in this window", so the composite index is
    # the access path rather than an optimisation.
    op.create_index(
        "ix_whatsapp_channel_events_type_time",
        "whatsapp_channel_events",
        ["event_type", "occurred_at"],
    )
    # Seam conversion asks "has this channel touched this case?" once per confirmed
    # payment on the whole platform, so it must not be a scan.
    op.create_index(
        "ix_whatsapp_channel_events_verification",
        "whatsapp_channel_events",
        ["verification_id"],
    )


def _add_page_code() -> None:
    op.add_column(
        "whatsapp_inbound_messages",
        sa.Column("page_code", sa.String(length=40), nullable=True),
    )
    # §7.10's voice-note volume is counted over a window off this table.
    op.create_index(
        "ix_whatsapp_inbound_kind_received",
        "whatsapp_inbound_messages",
        ["kind", "received_at"],
    )


def _create_whatsapp_number_health() -> None:
    op.create_table(
        "whatsapp_number_health",
        sa.Column("phone_number_id", sa.String(length=64), nullable=False),
        # Defaults to UNKNOWN rather than GREEN: the state before a first successful sync
        # must never read as a clean bill of health.
        sa.Column(
            "quality_rating",
            sa.String(length=16),
            nullable=False,
            server_default="UNKNOWN",
        ),
        # Meta's vocabulary, which they extend without notice — an enum here would turn a
        # new tier into a sync failure.
        sa.Column("messaging_limit_tier", sa.String(length=32), nullable=True),
        sa.Column("last_synced_at", UTCDateTime, nullable=True),
        # Kept rather than raised, so the admin surface can say "showing GREEN, but we
        # have not been able to ask since Tuesday".
        sa.Column("sync_error", sa.String(length=255), nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index(
        "ix_whatsapp_number_health_id", "whatsapp_number_health", ["id"], unique=True
    )
    op.create_index(
        "ix_whatsapp_number_health_phone_number_id",
        "whatsapp_number_health",
        ["phone_number_id"],
    )


def _seed_config() -> None:
    """Insert each key at its default; never overwrites an admin's edit."""
    conn = op.get_bind()
    for key, value, description in _CONFIG_ROWS:
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
    _create_whatsapp_channel_events()
    _add_page_code()
    _create_whatsapp_number_health()
    _seed_config()


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM system_config WHERE key = ANY(:keys)"),
        {"keys": [key for key, _value, _description in _CONFIG_ROWS]},
    )
    op.drop_table("whatsapp_number_health")
    op.drop_index("ix_whatsapp_inbound_kind_received", table_name="whatsapp_inbound_messages")
    op.drop_column("whatsapp_inbound_messages", "page_code")
    op.drop_table("whatsapp_channel_events")
