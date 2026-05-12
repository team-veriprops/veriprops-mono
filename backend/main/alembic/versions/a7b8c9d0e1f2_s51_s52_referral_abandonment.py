"""S51-S52 -- referral_codes, referral_redemptions tables; credit_balance_kobo
on users; abandonment_email_sent_at on verifications.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-05-12 08:01:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.alembic.utils import AlembicUtils
from main.appodus_utils.db.models import UTCDateTime

revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- referral_codes ------------------------------------------------
    op.create_table(
        "referral_codes",
        sa.Column("owner_id", sa.String(36), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("times_redeemed", sa.Integer, nullable=False, server_default="0"),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_referral_codes_id", "referral_codes", ["id"], unique=True)
    op.create_index("ix_referral_codes_owner_id", "referral_codes", ["owner_id"], unique=True)
    op.create_index("ix_referral_codes_code", "referral_codes", ["code"], unique=True)

    # -- referral_redemptions ------------------------------------------
    op.create_table(
        "referral_redemptions",
        sa.Column("referral_code_id", sa.String(36), nullable=False),
        sa.Column("invitee_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("credited_at", UTCDateTime, nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_referral_redemptions_id", "referral_redemptions", ["id"], unique=True)
    op.create_index("ix_referral_redemptions_invitee_id", "referral_redemptions", ["invitee_id"], unique=True)
    op.create_index("ix_referral_redemptions_code_id", "referral_redemptions", ["referral_code_id"])

    # -- users: credit balance -----------------------------------------
    op.add_column(
        "users",
        sa.Column("credit_balance_kobo", sa.BigInteger, nullable=False, server_default="0"),
    )

    # -- verifications: abandonment tracking ---------------------------
    op.add_column(
        "verifications",
        sa.Column("abandonment_email_sent_at", UTCDateTime, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("verifications", "abandonment_email_sent_at")
    op.drop_column("users", "credit_balance_kobo")
    for idx in [
        "ix_referral_redemptions_code_id",
        "ix_referral_redemptions_invitee_id",
        "ix_referral_redemptions_id",
    ]:
        op.drop_index(idx, table_name="referral_redemptions")
    op.drop_table("referral_redemptions")
    for idx in [
        "ix_referral_codes_code",
        "ix_referral_codes_owner_id",
        "ix_referral_codes_id",
    ]:
        op.drop_index(idx, table_name="referral_codes")
    op.drop_table("referral_codes")
