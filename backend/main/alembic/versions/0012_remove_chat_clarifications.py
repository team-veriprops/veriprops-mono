"""remove_chat_clarifications — structured clarifications are withdrawn (D89).

Additive, per decision D49 (`0001_initial_schema` is frozen).

Only the label of the §16.3 clarification flow was ever built: nothing relayed a request to
an agent, nothing sent a response, and nothing moved a request past ``OPEN``. The feature is
removed until it can be built end to end (PRD "Known Gaps & Roadmap"), so:

* every ``CLARIFICATION_REQUEST`` / ``CLARIFICATION_RESPONSE`` message becomes ``CHAT`` —
  its words stay in the thread exactly as sent, and ``MessageKind`` no longer has members to
  deserialise the old values into;
* ``chat_messages.clarification_status`` is dropped.

The kind conversion is one-way: ``downgrade`` restores the column (empty) but cannot tell
which ``CHAT`` rows were once clarifications.

Revision ID: 0012_remove_chat_clarifications
Revises: 0011_whatsapp_legal_copy
Create Date: 2026-09-16 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012_remove_chat_clarifications"
down_revision: Union[str, None] = "0011_whatsapp_legal_copy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _convert_clarification_messages_to_chat() -> None:
    # Raw strings, not app enums: migrations stay decoupled from `MessageKind`, which no
    # longer has these members.
    op.execute(
        "UPDATE chat_messages SET message_kind = 'CHAT' "
        "WHERE message_kind IN ('CLARIFICATION_REQUEST', 'CLARIFICATION_RESPONSE')"
    )


def _drop_clarification_status() -> None:
    op.drop_column("chat_messages", "clarification_status")


def _restore_clarification_status() -> None:
    op.add_column(
        "chat_messages", sa.Column("clarification_status", sa.String(length=16), nullable=True)
    )


def upgrade() -> None:
    _convert_clarification_messages_to_chat()
    _drop_clarification_status()


def downgrade() -> None:
    _restore_clarification_status()
