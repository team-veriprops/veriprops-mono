"""chat_channel_delivery — outbound delivery bookkeeping + §7.6.3 media labelling.

Additive, per decision D49 (`0001_initial_schema` is frozen).

Two nullable columns on ``chat_messages``, both serving the S7 console adapter:

* ``channel_delivered_at`` — when the message actually left over WhatsApp. Deliberately
  **not** a reuse of ``delivered_at``, which already means "released past the §4.7 fraud
  hold": conflating the two would make a held message look channel-delivered, and a
  message queued outside Meta's 24-hour window look lost. Null on an admin/agent message
  in a WhatsApp thread is what marks it as still waiting to go out.
* ``media_kind`` — what a non-text inbound actually was (§7.6.3), so the console can flag
  an image as unofficial and a voice note as audio without joining back to
  ``whatsapp_inbound_messages`` for every row it renders.

Both are null for every existing row, which is what they were: nothing had been delivered
over a channel, and every message was text.

Revision ID: 0007_chat_channel_delivery
Revises: 0006_whatsapp_bot_sessions
Create Date: 2026-09-02 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.appodus_utils.db.models import UTCDateTime

# revision identifiers, used by Alembic.
revision: str = "0007_chat_channel_delivery"
down_revision: Union[str, None] = "0006_whatsapp_bot_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_channel_delivery_bookkeeping() -> None:
    op.add_column("chat_messages", sa.Column("channel_delivered_at", UTCDateTime, nullable=True))
    # The queue read is "this thread's undelivered agent replies", so the index is on the
    # pair rather than on the timestamp alone.
    op.create_index(
        "ix_chat_messages_channel_pending",
        "chat_messages",
        ["conversation_id", "channel_delivered_at"],
    )


def _add_media_labelling() -> None:
    op.add_column("chat_messages", sa.Column("media_kind", sa.String(length=16), nullable=True))


def upgrade() -> None:
    _add_channel_delivery_bookkeeping()
    _add_media_labelling()


def downgrade() -> None:
    op.drop_column("chat_messages", "media_kind")
    op.drop_index("ix_chat_messages_channel_pending", table_name="chat_messages")
    op.drop_column("chat_messages", "channel_delivered_at")
