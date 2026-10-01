"""refund_requests — every return of a customer's money waits for Finance's approval.

Closing a paid case, an upheld dispute and a charge that lands on a case already closed each
file a refund request; a Finance admin approves it before anything moves at the gateway (§8.5,
§18.1). Alongside it:

* `payments.refund_due_minor` — what an approved refund still owes on a charge whose gateway
  refused it: Finance's refunds-to-retry list, and exactly what a retry sends. Recorded, where
  the list used to infer it from the case's status.
* `verifications.closure_reason` — why a paid case was closed; while the case waits on hold
  for Finance, it is what stops agents and the sweeps.

The backfill keeps today's refunds-to-retry list whole: a charge that list shows now (settled,
no chargeback, on a failed or refunded case) owed its whole amount, so that is what it still owes.

Revision ID: 0007_refund_requests
Revises: 0006_kyc_images
Create Date: 2026-09-30 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.alembic.utils import AlembicUtils
from main.appodus_utils.db.models import UTCDateTime

revision: str = "0007_refund_requests"
down_revision: Union[str, None] = "0006_kyc_images"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "refund_requests"


def _create_refund_requests() -> None:
    op.create_table(
        _TABLE,
        *AlembicUtils.base_audit_columns(),
        sa.Column("verification_id", sa.String(length=36), nullable=False),
        sa.Column("customer_id", sa.String(length=36), nullable=False),
        sa.Column("source", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("payment_id", sa.String(length=36), nullable=True),
        sa.Column("reason", sa.String(length=32), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("evidence_ref", sa.String(length=255), nullable=True),
        sa.Column("requested_by", sa.String(length=36), nullable=True),
        sa.Column("decided_by", sa.String(length=36), nullable=True),
        sa.Column("decided_at", UTCDateTime, nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
    )
    op.create_index("ix_refund_requests_verification_id", _TABLE, ["verification_id"])
    op.create_index("ix_refund_requests_status_date_created", _TABLE, ["status", "date_created"])
    op.create_index(
        "uq_refund_requests_pending_verification", _TABLE, ["verification_id"], unique=True,
        postgresql_where=sa.text("status = 'PENDING' AND source <> 'LATE_CHARGE' AND deleted = FALSE"),
    )


def upgrade() -> None:
    _create_refund_requests()
    op.add_column("payments", sa.Column("refund_due_minor", sa.BigInteger(), nullable=True))
    op.add_column("verifications", sa.Column("closure_reason", sa.String(length=32), nullable=True))

    op.execute("""
        UPDATE payments p SET refund_due_minor = p.amount_minor
        FROM verifications v
        WHERE replace(CAST(v.id AS VARCHAR), '-', '') = p.verification_id
          AND p.deleted = FALSE AND p.status = 'SUCCEEDED' AND p.chargeback_status IS NULL
          AND v.status IN ('FAILED', 'REFUNDED')
    """)


def downgrade() -> None:
    op.drop_column("verifications", "closure_reason")
    op.drop_column("payments", "refund_due_minor")
    op.drop_index("uq_refund_requests_pending_verification", table_name=_TABLE)
    op.drop_index("ix_refund_requests_status_date_created", table_name=_TABLE)
    op.drop_index("ix_refund_requests_verification_id", table_name=_TABLE)
    op.drop_table(_TABLE)
