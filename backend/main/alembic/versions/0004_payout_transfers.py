"""payout_transfers — payouts leave as real bank transfers.

A saved bank account now records the gateway's code for its bank and the gateway that
resolved the account name (bank codes are only meaningful to the gateway whose list they
came from). A payout snapshots both, carries the transfer fee deducted from what reaches
the bank, and tracks its current transfer attempt: our reference (unique, one per attempt,
so a retry is never mistaken for the transfer it replaces), the gateway's id for it, when
it was sent and settled, and why it failed.

Additive and nullable (or defaulted): accounts saved before resolution existed have no bank
code and must be added again before they can be paid; payouts from before have no transfer.

Revision ID: 0004_payout_transfers
Revises: 0003_payment_gateway_ref
Create Date: 2026-09-28 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.appodus_utils.db.models import UTCDateTime

revision: str = "0004_payout_transfers"
down_revision: Union[str, None] = "0003_payment_gateway_ref"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ACCOUNTS = "agent_bank_accounts"
_PAYOUTS = "payouts"
_REFERENCE_INDEX = "ix_payouts_transfer_reference"


def upgrade() -> None:
    op.add_column(_ACCOUNTS, sa.Column("bank_code", sa.String(length=16), nullable=True))
    op.add_column(_ACCOUNTS, sa.Column("provider", sa.String(length=32), nullable=True))

    op.add_column(_PAYOUTS, sa.Column("bank_code", sa.String(length=16), nullable=True))
    op.add_column(_PAYOUTS, sa.Column("provider", sa.String(length=32), nullable=True))
    op.add_column(_PAYOUTS, sa.Column("fee_minor", sa.BigInteger(), nullable=False, server_default="0"))
    op.add_column(_PAYOUTS, sa.Column("transfer_reference", sa.String(length=64), nullable=True))
    op.add_column(_PAYOUTS, sa.Column("gateway_transfer_id", sa.String(length=64), nullable=True))
    op.add_column(_PAYOUTS, sa.Column("transfer_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column(_PAYOUTS, sa.Column("sent_at", UTCDateTime, nullable=True))
    op.add_column(_PAYOUTS, sa.Column("settled_at", UTCDateTime, nullable=True))
    op.add_column(_PAYOUTS, sa.Column("failure_reason", sa.Text(), nullable=True))
    # Webhooks find a payout by the reference they cite; one reference is one attempt.
    op.create_index(_REFERENCE_INDEX, _PAYOUTS, ["transfer_reference"], unique=True)


def downgrade() -> None:
    # Loses the transfer trail only; the gateways still hold every transfer by our reference.
    op.drop_index(_REFERENCE_INDEX, table_name=_PAYOUTS)
    for column in ("failure_reason", "settled_at", "sent_at", "transfer_attempts", "gateway_transfer_id",
                   "transfer_reference", "fee_minor", "provider", "bank_code"):
        op.drop_column(_PAYOUTS, column)
    op.drop_column(_ACCOUNTS, "provider")
    op.drop_column(_ACCOUNTS, "bank_code")
