"""assistant_sessions — one assistant, keyed by conversation, on every surface (D93).

Additive, per decision D49 (`0001_initial_schema` is frozen).

The WhatsApp bot's per-number state becomes the surface-neutral assistant's per-conversation
state, so the same engine can answer a web support thread or a case thread as well as a
WhatsApp number. One helper per change:

* the table is renamed ``whatsapp_bot_sessions`` → ``chat_bot_sessions`` (declared in
  ``_TABLE_RENAMES`` for the schema-parity guard);
* ``conversation_id`` is added and backfilled from the number's WhatsApp conversation, then
  made the unique key. A session whose number has no conversation cannot exist through the
  application (the thread is created before the first turn); any such row is conversation
  working state with nothing to attach to, and is removed;
* ``phone_e164`` loses its uniqueness and becomes nullable — a web session has no number —
  keeping a plain index for the intake handoff and erasure, which find a session by number;
* ``pending_turn_message_id``, ``pending_turn_at`` and ``turn_claimed_at`` hold a web turn
  waiting for the intent model and the claim that keeps it single-shot.

Revision ID: 0015_assistant_sessions
Revises: 0014_chat_channel_status
Create Date: 2026-09-17 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.appodus_utils.db.models import UTCDateTime

# revision identifiers, used by Alembic.
revision: str = "0015_assistant_sessions"
down_revision: Union[str, None] = "0014_chat_channel_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (old, new) — read by test_migration_schema_parity so a rename is not mistaken for a dropped
# table plus an unbuilt one.
_TABLE_RENAMES = [("whatsapp_bot_sessions", "chat_bot_sessions")]


def _rename_table() -> None:
    op.drop_constraint("uq_whatsapp_bot_sessions_phone_e164", "whatsapp_bot_sessions", type_="unique")
    op.rename_table("whatsapp_bot_sessions", "chat_bot_sessions")
    op.execute("ALTER INDEX ix_whatsapp_bot_sessions_id RENAME TO ix_chat_bot_sessions_id")


def _key_by_conversation() -> None:
    op.add_column("chat_bot_sessions", sa.Column("conversation_id", sa.String(length=36), nullable=True))
    conn = op.get_bind()
    conn.execute(sa.text(
        """
        UPDATE chat_bot_sessions s
        SET conversation_id = REPLACE(CAST(c.id AS TEXT), '-', '')
        FROM conversations c
        WHERE c.channel = 'WHATSAPP' AND c.external_ref = s.phone_e164 AND c.deleted = FALSE
        """
    ))
    conn.execute(sa.text("DELETE FROM chat_bot_sessions WHERE conversation_id IS NULL"))
    op.alter_column("chat_bot_sessions", "conversation_id", nullable=False)
    op.create_unique_constraint(
        "uq_chat_bot_sessions_conversation_id", "chat_bot_sessions", ["conversation_id"]
    )


def _number_becomes_optional() -> None:
    op.alter_column("chat_bot_sessions", "phone_e164", nullable=True)
    op.create_index("ix_chat_bot_sessions_phone_e164", "chat_bot_sessions", ["phone_e164"], unique=False)


def _add_pending_turn() -> None:
    op.add_column("chat_bot_sessions", sa.Column("pending_turn_message_id", sa.String(length=36), nullable=True))
    op.add_column("chat_bot_sessions", sa.Column("pending_turn_at", UTCDateTime, nullable=True))
    op.add_column("chat_bot_sessions", sa.Column("turn_claimed_at", UTCDateTime, nullable=True))


def upgrade() -> None:
    _rename_table()
    _key_by_conversation()
    _number_becomes_optional()
    _add_pending_turn()


def downgrade() -> None:
    """Back to one row per number. Web sessions have no number and cannot exist there, so they
    are removed first; that loss is one-way."""
    op.drop_column("chat_bot_sessions", "turn_claimed_at")
    op.drop_column("chat_bot_sessions", "pending_turn_at")
    op.drop_column("chat_bot_sessions", "pending_turn_message_id")
    op.execute("DELETE FROM chat_bot_sessions WHERE phone_e164 IS NULL")
    op.drop_index("ix_chat_bot_sessions_phone_e164", table_name="chat_bot_sessions")
    op.alter_column("chat_bot_sessions", "phone_e164", nullable=False)
    op.drop_constraint("uq_chat_bot_sessions_conversation_id", "chat_bot_sessions", type_="unique")
    op.drop_column("chat_bot_sessions", "conversation_id")
    op.execute("ALTER INDEX ix_chat_bot_sessions_id RENAME TO ix_whatsapp_bot_sessions_id")
    op.rename_table("chat_bot_sessions", "whatsapp_bot_sessions")
    op.create_unique_constraint(
        "uq_whatsapp_bot_sessions_phone_e164", "whatsapp_bot_sessions", ["phone_e164"]
    )
