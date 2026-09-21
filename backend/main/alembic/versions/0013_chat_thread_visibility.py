"""chat_thread_visibility — a customer can see their WhatsApp thread, within a window.

Additive, per decision D49 (`0001_initial_schema` is frozen).

The portal's conversation list is membership-driven, and linking a WhatsApp number used to
give its thread an owner (`conversations.created_by`) without making that owner a member —
so a linked customer never saw their own thread. A membership now carries a **visibility
window**:

* ``visible_from`` — the customer sees the thread from the moment they linked the number;
  earlier messages may belong to a previous holder of it;
* ``visible_until`` — set when the number is released; the history up to then stays
  readable, and the thread goes read-only for them.

Both are null for every web membership, which keeps reading the whole thread.

Backfill, one helper each:

* every number already ACTIVE-linked gets its owner enrolled (or an existing membership
  reopened) from ``linked_at``;
* any other non-admin membership on a WhatsApp thread is closed with an empty window. The
  only way one existed was the pre-D89 `/portal/support` lookup, which could open a linked
  customer's WhatsApp thread by mistake — it never granted a right to read it.

Revision ID: 0013_chat_thread_visibility
Revises: 0012_remove_chat_clarifications
Create Date: 2026-09-16 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.alembic.utils import AlembicUtils

from main.appodus_utils import Utils
from main.appodus_utils.db.models import UTCDateTime

# revision identifiers, used by Alembic.
revision: str = "0013_chat_thread_visibility"
down_revision: Union[str, None] = "0012_remove_chat_clarifications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_visibility_window() -> None:
    op.add_column("conversation_participants", sa.Column("visible_from", UTCDateTime, nullable=True))
    op.add_column("conversation_participants", sa.Column("visible_until", UTCDateTime, nullable=True))


def _enrol_linked_owners() -> None:
    """Make every ACTIVE link's owner a member of its number's thread, from ``linked_at``."""
    conn = op.get_bind()
    now = Utils.datetime_now()
    owners = conn.execute(sa.text(
        """
        SELECT c.id AS conversation_id, l.user_id, l.linked_at
        FROM whatsapp_links l
        JOIN conversations c
          ON c.channel = 'WHATSAPP' AND c.external_ref = l.phone_e164 AND c.deleted = FALSE
        WHERE l.status = 'ACTIVE' AND l.phone_e164 IS NOT NULL AND l.deleted = FALSE
        """
    )).all()
    for conversation_id, user_id, linked_at in owners:
        # Participant rows reference a conversation by its 32-char hex id.
        conversation_ref = Utils.uuid_to_hex(conversation_id)
        visible_from = linked_at or now
        conn.execute(
            sa.text("UPDATE conversations SET created_by = :user_id WHERE id = :id"),
            {"user_id": user_id, "id": conversation_id},
        )
        reopened = conn.execute(
            sa.text(
                "UPDATE conversation_participants "
                "SET visible_from = :visible_from, visible_until = NULL "
                "WHERE conversation_id = :conversation_id AND user_id = :user_id AND deleted = FALSE"
            ),
            {"visible_from": visible_from, "conversation_id": conversation_ref, "user_id": user_id},
        )
        if reopened.rowcount:
            continue
        conn.execute(
            sa.text(
                "INSERT INTO conversation_participants "
                "(id, conversation_id, user_id, role, visible_from, date_created, deleted, version) "
                "VALUES (:id, :conversation_id, :user_id, 'CUSTOMER', :visible_from, :now, FALSE, 1)"
            ),
            {
                "id": Utils.generate_uuid(),
                "conversation_id": conversation_ref,
                "user_id": user_id,
                "visible_from": visible_from,
                "now": now,
            },
        )


def _close_unowned_customer_memberships() -> None:
    """Close, with an empty window, non-admin memberships on WhatsApp threads that no link
    justifies. Runs after `_enrol_linked_owners`, so every rightful owner already has a
    ``visible_from`` and is untouched here."""
    op.get_bind().execute(
        sa.text(
            """
            UPDATE conversation_participants p
            SET visible_from = :now, visible_until = :now
            FROM conversations c, users u
            WHERE c.id = CAST(p.conversation_id AS uuid)
              AND c.channel = 'WHATSAPP'
              AND u.id = CAST(p.user_id AS uuid)
              AND u.user_type <> 'ADMIN'
              AND p.visible_from IS NULL
              AND p.deleted = FALSE
            """
        ),
        {"now": Utils.datetime_now()},
    )


def upgrade() -> None:
    _add_visibility_window()
    # Enrolment rewrites `created_by`; it must never replace a different, existing owner.
    AlembicUtils.refuse_if_rows(
        """
        SELECT count(*) FROM whatsapp_links l
        JOIN conversations c
          ON c.channel = 'WHATSAPP' AND c.external_ref = l.phone_e164 AND c.deleted = FALSE
        WHERE l.status = 'ACTIVE' AND l.phone_e164 IS NOT NULL AND l.deleted = FALSE
          AND c.created_by IS NOT NULL AND c.created_by <> l.user_id
        """,
        "WhatsApp threads whose existing owner enrolment would overwrite",
    )
    _enrol_linked_owners()
    _close_unowned_customer_memberships()


def downgrade() -> None:
    op.drop_column("conversation_participants", "visible_until")
    op.drop_column("conversation_participants", "visible_from")
