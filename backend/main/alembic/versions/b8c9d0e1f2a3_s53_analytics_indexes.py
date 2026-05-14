"""S53 -- covering indexes for analytics aggregation queries.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-05-14 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_verifications_status_tier", "verifications", ["status", "tier"])
    op.create_index("ix_verifications_paid_completed", "verifications", ["paid_at", "completed_at"])
    op.create_index("ix_tasks_status_accepted_at", "tasks", ["status", "accepted_at"])
    op.create_index("ix_payments_status_amount", "payments", ["status", "amount_minor"])


def downgrade() -> None:
    op.drop_index("ix_payments_status_amount", table_name="payments")
    op.drop_index("ix_tasks_status_accepted_at", table_name="tasks")
    op.drop_index("ix_verifications_paid_completed", table_name="verifications")
    op.drop_index("ix_verifications_status_tier", table_name="verifications")
