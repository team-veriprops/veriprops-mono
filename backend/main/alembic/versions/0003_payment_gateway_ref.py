"""payment_gateway_ref — the gateway's own reference for a charge, on the payment.

Every live charge is confirmed by asking the gateway about it, and the answer carries the
gateway's own handle for the charge besides our ``tx_ref``: Flutterwave's ``flw_ref``, Paystack's
transaction id. Flutterwave's chargeback webhooks name the disputed charge **only** by
``flw_ref``, so without this column a dispute could not be matched to its payment.

The column is provider-neutral, nullable and additive: stub-mode payments and every payment
made before the live gateways were wired simply have none.

Revision ID: 0003_payment_gateway_ref
Revises: 0002_fixed_agent_commission
Create Date: 2026-09-27 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_payment_gateway_ref"
down_revision: Union[str, None] = "0002_fixed_agent_commission"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "payments"
_COLUMN = "gateway_reference"
_INDEX = "ix_payments_gateway_reference"


def upgrade() -> None:
    op.add_column(_TABLE, sa.Column(_COLUMN, sa.String(length=128), nullable=True))
    op.create_index(_INDEX, _TABLE, [_COLUMN])


def downgrade() -> None:
    # Only a lookup handle is lost; the gateway still holds it against our tx_ref.
    op.drop_index(_INDEX, table_name=_TABLE)
    op.drop_column(_TABLE, _COLUMN)
