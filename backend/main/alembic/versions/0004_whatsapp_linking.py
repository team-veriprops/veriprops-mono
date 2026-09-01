"""whatsapp_linking — the channel's identity seam, and link-shaped handoff tokens.

Additive, per decision D49 (`0001_initial_schema` is frozen).

Adds:
* ``whatsapp_links`` — one row per account, one number per row. Both unique constraints
  are load-bearing rather than hygiene: they are what enforce §7.4.4's one-to-one rule,
  so no caller can create a second live number for an account by forgetting to check.
  ``phone_e164`` is nullable because an unlink **clears** it — a revoked row that kept its
  number would hold the unique constraint and lock that number out of every other account
  forever.
* ``handoff_token_redemptions.case_id`` widened to nullable, plus ``phone_e164`` — a
  ``link`` token names a phone number instead of a case (D55). Widening NOT NULL → NULL is
  safe on existing rows, which all carry a case.

Revision ID: 0004_whatsapp_linking
Revises: 0003_handoff_tokens
Create Date: 2026-09-01 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.alembic.utils import AlembicUtils
from main.appodus_utils.db.models import UTCDateTime

# revision identifiers, used by Alembic.
revision: str = "0004_whatsapp_linking"
down_revision: Union[str, None] = "0003_handoff_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Raw strings by design — migrations stay decoupled from app enums.
_STATUS_PENDING = "PENDING"


def _create_whatsapp_links() -> None:
    op.create_table(
        "whatsapp_links",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        # Null once revoked, which is what releases the number for another account.
        sa.Column("phone_e164", sa.String(length=32), nullable=True),
        sa.Column("wa_id", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=10), nullable=False, server_default=_STATUS_PENDING),
        sa.Column("linked_at", UTCDateTime, nullable=True),
        sa.Column("revoked_at", UTCDateTime, nullable=True),
        sa.Column("revoked_reason", sa.String(length=120), nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_whatsapp_links_id", "whatsapp_links", ["id"], unique=True)
    # The §7.4.4 one-to-one rule, enforced in the database rather than by convention.
    op.create_unique_constraint("uq_whatsapp_links_user_id", "whatsapp_links", ["user_id"])
    op.create_unique_constraint("uq_whatsapp_links_phone_e164", "whatsapp_links", ["phone_e164"])


def _widen_handoff_redemptions_for_link_tokens() -> None:
    op.alter_column(
        "handoff_token_redemptions", "case_id",
        existing_type=sa.String(length=36), nullable=True,
    )
    op.add_column(
        "handoff_token_redemptions",
        sa.Column("phone_e164", sa.String(length=32), nullable=True),
    )


def upgrade() -> None:
    _create_whatsapp_links()
    _widen_handoff_redemptions_for_link_tokens()


def downgrade() -> None:
    op.drop_column("handoff_token_redemptions", "phone_e164")
    # Every surviving row that carries no case is a `link` redemption, which cannot exist
    # under the narrowed column; drop those rather than fail the constraint.
    op.execute("DELETE FROM handoff_token_redemptions WHERE case_id IS NULL")
    op.alter_column(
        "handoff_token_redemptions", "case_id",
        existing_type=sa.String(length=36), nullable=False,
    )
    op.drop_table("whatsapp_links")
