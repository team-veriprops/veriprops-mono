"""whatsapp_consent — the §7.4.6 opt-in ledger the notification router enforces.

Additive, per decision D49 (`0001_initial_schema` is frozen).

Adds ``whatsapp_consents``: one row per account holding both §7.4.6 controls (D63).

Two shape decisions are load-bearing rather than cosmetic:

* **Each consent keeps a grant *and* a revoke timestamp, and no boolean.** §7.8 requires
  consent records to be timestamped and exportable, so the pair of stamps *is* the record
  and "granted" is derived from it — a stored flag beside them could only ever drift from
  the evidence that justifies it.
* **One row, two consents.** They are captured together on one screen and revoked together
  by a STOP keyword (D64), so splitting them into a row each would buy nothing and make
  every read a join.

Every column is nullable and there is no backfill: an account with no row has consented to
nothing, which is exactly what §7.4.6's unticked default means.

Revision ID: 0008_whatsapp_consent
Revises: 0007_chat_channel_delivery
Create Date: 2026-09-02 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.alembic.utils import AlembicUtils
from main.appodus_utils.db.models import UTCDateTime

# revision identifiers, used by Alembic.
revision: str = "0008_whatsapp_consent"
down_revision: Union[str, None] = "0007_chat_channel_delivery"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_whatsapp_consents() -> None:
    op.create_table(
        "whatsapp_consents",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        # "Send me progress updates about this verification on WhatsApp" (§7.4.6 #1).
        sa.Column("utility_granted_at", UTCDateTime, nullable=True),
        sa.Column("utility_revoked_at", UTCDateTime, nullable=True),
        sa.Column("utility_source", sa.String(length=24), nullable=True),
        # "Send me occasional Veriprops news and offers on WhatsApp" (§7.4.6 #2).
        sa.Column("marketing_granted_at", UTCDateTime, nullable=True),
        sa.Column("marketing_revoked_at", UTCDateTime, nullable=True),
        sa.Column("marketing_source", sa.String(length=24), nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_whatsapp_consents_id", "whatsapp_consents", ["id"], unique=True)
    # One consent state per account: two concurrent captures must not leave the router
    # choosing between two answers to the same question.
    op.create_unique_constraint(
        "uq_whatsapp_consents_user_id", "whatsapp_consents", ["user_id"]
    )


def upgrade() -> None:
    _create_whatsapp_consents()


def downgrade() -> None:
    op.drop_table("whatsapp_consents")
