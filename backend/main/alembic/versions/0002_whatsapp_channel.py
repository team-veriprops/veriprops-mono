"""whatsapp_channel — inbound journal + conversation/message source labeling.

The first additive migration of the WhatsApp cycle. `0001_initial_schema` is now frozen:
it creates tables only when they are absent, so a column added there would silently never
appear on an already-migrated database (decision D49).

Adds:
* ``whatsapp_inbound_messages`` — the journal every Meta delivery lands in. The unique
  index on ``wamid`` is load-bearing, not hygiene: it is what makes Meta's redelivery a
  no-op, which in turn is what lets the webhook acknowledge everything it authenticates.
* source labeling on the existing conversation pipeline, so a WhatsApp thread and its
  messages are distinguishable in the admin console without becoming a separate pipeline.

Server defaults are set so every existing row reads as WEB, which is what it was.

Revision ID: 0002_whatsapp_channel
Revises: 0003_user_verify_started
Create Date: 2026-08-31 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.alembic.utils import AlembicUtils
from main.appodus_utils.db.models import UTCDateTime, JSONB_VARIANT

# revision identifiers, used by Alembic.
revision: str = "0002_whatsapp_channel"
down_revision: Union[str, None] = "0003_user_verify_started"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Raw strings by design — migrations stay decoupled from app enums.
_CHANNEL_WEB = "WEB"
_SOURCE_WEB = "WEB"


def _create_whatsapp_inbound_messages() -> None:
    op.create_table(
        "whatsapp_inbound_messages",
        sa.Column("wamid", sa.String(length=128), nullable=False),
        sa.Column("from_phone", sa.String(length=20), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("interactive_id", sa.String(length=64), nullable=True),
        sa.Column("media_id", sa.String(length=128), nullable=True),
        sa.Column("media_mime_type", sa.String(length=100), nullable=True),
        sa.Column("sender_name", sa.String(length=120), nullable=True),
        sa.Column("payload", JSONB_VARIANT, nullable=True),
        sa.Column("received_at", UTCDateTime, nullable=True),
        sa.Column("processed_at", UTCDateTime, nullable=True),
        sa.Column("chat_message_id", sa.String(length=36), nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_whatsapp_inbound_messages_id", "whatsapp_inbound_messages", ["id"], unique=True)
    op.create_index("ix_whatsapp_inbound_from_phone", "whatsapp_inbound_messages", ["from_phone"], unique=False)
    op.create_index(
        "ix_whatsapp_inbound_messages_chat_message_id",
        "whatsapp_inbound_messages", ["chat_message_id"], unique=False,
    )
    # Exactly-once ingestion: a Meta redelivery collides here instead of producing a
    # duplicate conversation turn.
    op.create_unique_constraint("uq_whatsapp_inbound_wamid", "whatsapp_inbound_messages", ["wamid"])


def _add_conversation_source_labeling() -> None:
    op.add_column(
        "conversations",
        sa.Column("channel", sa.String(length=10), nullable=False, server_default=_CHANNEL_WEB),
    )
    # The sender's E.164 number for a WhatsApp thread — how an inbound message finds its
    # existing thread before the number is linked to an account.
    op.add_column("conversations", sa.Column("external_ref", sa.String(length=20), nullable=True))
    op.create_index("ix_conversations_external_ref", "conversations", ["external_ref"], unique=False)


def _add_chat_message_source_labeling() -> None:
    op.add_column(
        "chat_messages",
        sa.Column("source", sa.String(length=10), nullable=False, server_default=_SOURCE_WEB),
    )
    op.add_column(
        "chat_messages", sa.Column("external_message_id", sa.String(length=128), nullable=True)
    )


def upgrade() -> None:
    # No table_exists guards here, unlike 0001: that migration carries them because it
    # was squashed over databases that already held some of its tables. An additive
    # revision runs exactly once, tracked by alembic's version table — and the guards
    # would also make this migration unusable in offline (`--sql`) mode.
    _create_whatsapp_inbound_messages()
    _add_conversation_source_labeling()
    _add_chat_message_source_labeling()


def downgrade() -> None:
    op.drop_column("chat_messages", "external_message_id")
    op.drop_column("chat_messages", "source")
    op.drop_index("ix_conversations_external_ref", table_name="conversations")
    op.drop_column("conversations", "external_ref")
    op.drop_column("conversations", "channel")
    op.drop_table("whatsapp_inbound_messages")
