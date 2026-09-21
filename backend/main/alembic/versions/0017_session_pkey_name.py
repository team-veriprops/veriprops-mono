"""session_pkey_name — carry the table rename through to its primary key's name.

Additive, per decision D49 (`0001_initial_schema` is frozen).

`0015_assistant_sessions` renamed `whatsapp_bot_sessions` to `chat_bot_sessions`, but Postgres
keeps a constraint's name through `ALTER TABLE ... RENAME`, so every migrated database still
calls the primary key `whatsapp_bot_sessions_pkey` while a freshly built one calls it
`chat_bot_sessions_pkey`. Harmless at runtime and invisible until something addresses the
constraint by name — at which point it fails on exactly the environments that matter.

It also blocks the next squash: folding the chain into `0001` is only honest if a database
that migrated through it is indistinguishable from one built in one step, and this is the one
difference that survives (column *order* also differs, which no DDL can address by name and
nothing reads positionally).

Written so it holds whichever name the database happens to carry.

Revision ID: 0017_session_pkey_name
Revises: 0016_participant_unique
Create Date: 2026-09-21 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0017_session_pkey_name"
down_revision: Union[str, None] = "0016_participant_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LEGACY = "whatsapp_bot_sessions_pkey"
_CURRENT = "chat_bot_sessions_pkey"


def _rename_constraint(old: str, new: str) -> None:
    """Rename the primary key only when it still carries *old* — a database built after the
    squash already has *new*, and this must be a no-op there rather than an error."""
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = '{old}'
                  AND conrelid = 'chat_bot_sessions'::regclass
            ) THEN
                ALTER TABLE chat_bot_sessions RENAME CONSTRAINT {old} TO {new};
            END IF;
        END $$;
        """
    )


def upgrade() -> None:
    _rename_constraint(_LEGACY, _CURRENT)


def downgrade() -> None:
    _rename_constraint(_CURRENT, _LEGACY)
