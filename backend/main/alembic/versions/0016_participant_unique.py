"""participant_unique — one live membership per (conversation, user).

Additive, per decision D49 (`0001_initial_schema` is frozen).

``conversation_participants`` had no uniqueness, and two requests opening the same thread
at once (a thread mark-read racing the reply that follows it) both saw "not a member yet"
and both inserted. The duplicate then doubled that member's row in every list that joins
memberships, the admin Conversations inbox first. One helper per change:

* ``_merge_duplicate_memberships`` — keeps the earliest row per (conversation, user), carrying
  the latest ``last_read_at`` onto it so no read state is lost, and deletes the rest;
* ``_enforce_one_membership`` — a partial unique index over live rows, so a soft-deleted
  membership never blocks a fresh one.

Revision ID: 0016_participant_unique
Revises: 0015_assistant_sessions
Create Date: 2026-09-21 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0016_participant_unique"
down_revision: Union[str, None] = "0015_assistant_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEX = "uq_conv_participants_membership"


def _merge_duplicate_memberships() -> None:
    op.execute(
        """
        UPDATE conversation_participants p
        SET last_read_at = d.latest_read
        FROM (
            SELECT conversation_id, user_id, MAX(last_read_at) AS latest_read
            FROM conversation_participants
            WHERE deleted = FALSE
            GROUP BY conversation_id, user_id
            HAVING COUNT(*) > 1
        ) d
        WHERE p.conversation_id = d.conversation_id
          AND p.user_id = d.user_id
          AND p.deleted = FALSE
        """
    )
    op.execute(
        """
        DELETE FROM conversation_participants
        WHERE id IN (
            SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (
                    PARTITION BY conversation_id, user_id ORDER BY date_created, id
                ) AS position
                FROM conversation_participants
                WHERE deleted = FALSE
            ) ranked
            WHERE position > 1
        )
        """
    )


def _enforce_one_membership() -> None:
    op.execute(
        f"CREATE UNIQUE INDEX {_INDEX} ON conversation_participants (conversation_id, user_id) "
        "WHERE deleted = FALSE"
    )


def upgrade() -> None:
    _merge_duplicate_memberships()
    _enforce_one_membership()


def downgrade() -> None:
    """The index goes; the merged duplicates were redundant rows and are not restored."""
    op.execute(f"DROP INDEX IF EXISTS {_INDEX}")
