"""chat_channel_status — WhatsApp delivery and read receipts on chat messages (D92).

Additive, per decision D49 (`0001_initial_schema` is frozen).

Every outbound WhatsApp text is stored with the wamid Meta returned, and Meta's receipts for
that wamid move the message forward. One helper per change:

* ``chat_messages.channel_status`` / ``channel_status_at`` — ``SENT → DELIVERED → READ``,
  ``FAILED``, or ``CANCELLED`` (a queued reply the customer read in the portal first);
* an index on ``chat_messages.external_message_id`` — a receipt finds its message by wamid;
* an index on ``messages.provider_id`` — the same receipt updates the bookkeeping row;
* backfill: a reply already carried out over WhatsApp (``channel_delivered_at`` set) reads as
  ``SENT``. It has no wamid, so no receipt will ever move it further.

Revision ID: 0014_chat_channel_status
Revises: 0013_chat_thread_visibility
Create Date: 2026-09-17 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.appodus_utils.db.models import UTCDateTime

# revision identifiers, used by Alembic.
revision: str = "0014_chat_channel_status"
down_revision: Union[str, None] = "0013_chat_thread_visibility"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_channel_status() -> None:
    op.add_column("chat_messages", sa.Column("channel_status", sa.String(length=12), nullable=True))
    op.add_column("chat_messages", sa.Column("channel_status_at", UTCDateTime, nullable=True))


def _index_receipt_lookups() -> None:
    op.create_index(
        "ix_chat_messages_external_message_id", "chat_messages", ["external_message_id"], unique=False
    )
    op.create_index("ix_messages_provider_id", "messages", ["provider_id"], unique=False)


def _backfill_sent_replies() -> None:
    op.get_bind().execute(sa.text(
        """
        UPDATE chat_messages
        SET channel_status = 'SENT', channel_status_at = channel_delivered_at
        WHERE channel_delivered_at IS NOT NULL AND channel_status IS NULL
        """
    ))


def upgrade() -> None:
    _add_channel_status()
    _index_receipt_lookups()
    _backfill_sent_replies()


def downgrade() -> None:
    op.drop_index("ix_messages_provider_id", table_name="messages")
    op.drop_index("ix_chat_messages_external_message_id", table_name="chat_messages")
    op.drop_column("chat_messages", "channel_status_at")
    op.drop_column("chat_messages", "channel_status")
