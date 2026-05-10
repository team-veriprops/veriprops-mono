"""add kyc_records table — S8 KYC BVN + selfie integration

Adds:
- kyc_records: per-event KYC audit trail (BVN verification + async selfie match)
  Tracks status lifecycle: PENDING → PASSED | FAILED | UNDER_REVIEW
  Admin review fields for low-confidence selfie results (D18).

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-05-07 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.appodus_utils.db.models import UTCDateTime

revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "kyc_records",
        sa.Column("id", sa.String(36), nullable=False, primary_key=True),
        sa.Column("date_created", UTCDateTime, nullable=False),
        sa.Column("date_updated", UTCDateTime, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, default=1),
        sa.Column("deleted", sa.Boolean, nullable=False, default=False),
        # Domain fields
        sa.Column("application_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("kyc_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_ref", sa.String(128), nullable=True),
        sa.Column("score", sa.Integer, nullable=True),
        sa.Column("failure_reason", sa.Text, nullable=True),
        sa.Column("webhook_payload", sa.JSON, nullable=True),
        sa.Column("reviewed_by_admin_id", sa.String(36), nullable=True),
        sa.Column("reviewed_at", UTCDateTime, nullable=True),
        sa.Column("admin_decision", sa.String(8), nullable=True),
        sa.Column("admin_notes", sa.Text, nullable=True),
    )
    op.create_index("ix_kyc_records_application_id", "kyc_records", ["application_id"])
    op.create_index("ix_kyc_records_user_id", "kyc_records", ["user_id"])
    op.create_index("ix_kyc_records_status", "kyc_records", ["status"])
    op.create_index("ix_kyc_records_provider_ref", "kyc_records", ["provider_ref"])
    op.create_index("ix_kyc_records_app_type", "kyc_records", ["application_id", "kyc_type"])


def downgrade() -> None:
    op.drop_index("ix_kyc_records_app_type", table_name="kyc_records")
    op.drop_index("ix_kyc_records_provider_ref", table_name="kyc_records")
    op.drop_index("ix_kyc_records_status", table_name="kyc_records")
    op.drop_index("ix_kyc_records_user_id", table_name="kyc_records")
    op.drop_index("ix_kyc_records_application_id", table_name="kyc_records")
    op.drop_table("kyc_records")
