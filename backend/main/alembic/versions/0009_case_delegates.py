"""case_delegates — the §7.4.5 per-case, status-only, revocable grant.

Additive, per decision D49 (`0001_initial_schema` is frozen).

Adds ``case_delegates``: at most one live delegate per verification (D67).

Two shape decisions carry the rule:

* **The number lives here, not in ``whatsapp_links``.** A delegate has no account, so
  reusing the link table would either break its one-account-one-number constraints or
  hand a delegate an account-shaped identity. The bot's resolution order — account first,
  delegate second — depends on the two being separable.
* **"One per case" is a partial unique index, not a plain one.** Uniqueness has to apply
  to *live* rows only: a revoked delegate must not block the buyer from authorizing a
  replacement, and the revoked row is kept because "who could see this, and until when"
  is the question a disputed verification eventually asks.

``verified_at`` is null until the delegate answers their OTP, and every read that grants
anything requires it — an authorization nobody confirmed is an attempt, not a grant.

Revision ID: 0009_case_delegates
Revises: 0008_whatsapp_consent
Create Date: 2026-09-02 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.alembic.utils import AlembicUtils
from main.appodus_utils.db.models import UTCDateTime

# revision identifiers, used by Alembic.
revision: str = "0009_case_delegates"
down_revision: Union[str, None] = "0008_whatsapp_consent"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_case_delegates() -> None:
    op.create_table(
        "case_delegates",
        sa.Column("verification_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("phone_e164", sa.String(length=32), nullable=False),
        # Null until the OTP is confirmed — nothing is visible before that moment.
        sa.Column("verified_at", UTCDateTime, nullable=True),
        sa.Column("revoked_at", UTCDateTime, nullable=True),
        sa.Column("revoked_reason", sa.String(length=120), nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_case_delegates_id", "case_delegates", ["id"], unique=True)
    # The two lookups: the buyer's case page, and the bot resolving an inbound number.
    op.create_index("ix_case_delegates_verification", "case_delegates", ["verification_id"])
    op.create_index("ix_case_delegates_phone", "case_delegates", ["phone_e164"])
    # §7.4.5's one-delegate-per-case rule, enforced in the database over *live* rows only.
    # A plain unique constraint would make the first revocation permanent.
    op.create_index(
        "uq_case_delegates_live_per_case",
        "case_delegates",
        ["verification_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL AND deleted = false"),
    )


def upgrade() -> None:
    _create_case_delegates()


def downgrade() -> None:
    op.drop_table("case_delegates")
