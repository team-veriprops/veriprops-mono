"""S43-S48 -- share_links, share_recipients, recheck_requests, tier_upgrades,
disputes, dispute_resolutions, commission_rules, earnings,
bank_accounts, payouts, payout_adjustments tables.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-12 00:02:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.alembic.utils import AlembicUtils
from main.appodus_utils.db.models import UTCDateTime

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- share_links -----------------------------------------------
    op.create_table(
        "share_links",
        sa.Column("verification_id", sa.String(36), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False, default="PRIVATE"),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("expires_at", UTCDateTime, nullable=True),
        sa.Column("revoked_at", UTCDateTime, nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_share_links_id", "share_links", ["id"], unique=True)
    op.create_index("ix_share_links_token", "share_links", ["token"], unique=True)
    op.create_index("ix_share_links_verification_id", "share_links", ["verification_id"])

    # -- share_recipients ------------------------------------------
    op.create_table(
        "share_recipients",
        sa.Column("share_link_id", sa.String(36), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("acknowledged_at", UTCDateTime, nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_share_recipients_id", "share_recipients", ["id"], unique=True)
    op.create_index("ix_share_recipients_link_id", "share_recipients", ["share_link_id"])

    # -- recheck_requests ------------------------------------------
    op.create_table(
        "recheck_requests",
        sa.Column("verification_id", sa.String(36), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("scope_roles", sa.Text, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, default="PENDING"),
        sa.Column("requested_by", sa.String(36), nullable=False),
        sa.Column("reviewed_by", sa.String(36), nullable=True),
        sa.Column("reviewed_at", UTCDateTime, nullable=True),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_recheck_requests_id", "recheck_requests", ["id"], unique=True)
    op.create_index("ix_recheck_requests_verification_id", "recheck_requests", ["verification_id"])

    # -- tier_upgrades ---------------------------------------------
    op.create_table(
        "tier_upgrades",
        sa.Column("verification_id", sa.String(36), nullable=False),
        sa.Column("from_tier", sa.String(16), nullable=False),
        sa.Column("to_tier", sa.String(16), nullable=False),
        sa.Column("delta_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, default="PENDING"),
        sa.Column("requested_by", sa.String(36), nullable=False),
        sa.Column("payment_id", sa.String(36), nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_tier_upgrades_id", "tier_upgrades", ["id"], unique=True)
    op.create_index("ix_tier_upgrades_verification_id", "tier_upgrades", ["verification_id"])

    # -- disputes --------------------------------------------------
    op.create_table(
        "disputes",
        sa.Column("verification_id", sa.String(36), nullable=False),
        sa.Column("dispute_type", sa.String(40), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, default="PENDING"),
        sa.Column("submitted_by", sa.String(36), nullable=False),
        sa.Column("submitted_at", UTCDateTime, nullable=False),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_disputes_id", "disputes", ["id"], unique=True)
    op.create_index("ix_disputes_verification_id", "disputes", ["verification_id"])

    # -- dispute_resolutions ---------------------------------------
    op.create_table(
        "dispute_resolutions",
        sa.Column("dispute_id", sa.String(36), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("resolution_note", sa.Text, nullable=True),
        sa.Column("resolved_by", sa.String(36), nullable=False),
        sa.Column("resolved_at", UTCDateTime, nullable=False),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_dispute_resolutions_id", "dispute_resolutions", ["id"], unique=True)
    op.create_index("ix_dispute_resolutions_dispute_id", "dispute_resolutions", ["dispute_id"])

    # -- commission_rules ------------------------------------------
    op.create_table(
        "commission_rules",
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("tier", sa.String(16), nullable=False),
        sa.Column("percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("effective_date", sa.Date, nullable=False),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_commission_rules_id", "commission_rules", ["id"], unique=True)
    op.create_index("ix_commission_rules_role_tier", "commission_rules", ["role", "tier"])

    # -- earnings --------------------------------------------------
    op.create_table(
        "earnings",
        sa.Column("agent_id", sa.String(36), nullable=False),
        sa.Column("task_id", sa.String(36), nullable=False),
        sa.Column("verification_id", sa.String(36), nullable=False),
        sa.Column("gross_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("commission_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("net_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, default="PENDING"),
        sa.Column("computed_at", UTCDateTime, nullable=False),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_earnings_id", "earnings", ["id"], unique=True)
    op.create_index("ix_earnings_agent_id", "earnings", ["agent_id"])
    op.create_index("ix_earnings_task_id", "earnings", ["task_id"])

    # -- bank_accounts ---------------------------------------------
    op.create_table(
        "bank_accounts",
        sa.Column("agent_id", sa.String(36), nullable=False),
        sa.Column("bank_name", sa.String(100), nullable=False),
        sa.Column("account_number", sa.String(20), nullable=False),
        sa.Column("account_holder_name", sa.String(200), nullable=False),
        sa.Column("is_default", sa.Boolean, nullable=False, default=False),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_bank_accounts_id", "bank_accounts", ["id"], unique=True)
    op.create_index("ix_bank_accounts_agent_id", "bank_accounts", ["agent_id"])

    # -- payouts ---------------------------------------------------
    op.create_table(
        "payouts",
        sa.Column("agent_id", sa.String(36), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("bank_account_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, default="PENDING"),
        sa.Column("requested_at", UTCDateTime, nullable=False),
        sa.Column("approved_at", UTCDateTime, nullable=True),
        sa.Column("paid_at", UTCDateTime, nullable=True),
        sa.Column("hold_reason", sa.Text, nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_payouts_id", "payouts", ["id"], unique=True)
    op.create_index("ix_payouts_agent_id", "payouts", ["agent_id"])

    # -- payout_adjustments ----------------------------------------
    op.create_table(
        "payout_adjustments",
        sa.Column("payout_id", sa.String(36), nullable=False),
        sa.Column("adjusted_by", sa.String(36), nullable=False),
        sa.Column("original_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("new_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_payout_adjustments_id", "payout_adjustments", ["id"], unique=True)
    op.create_index("ix_payout_adjustments_payout_id", "payout_adjustments", ["payout_id"])


def downgrade() -> None:
    for tbl, idxs in [
        ("payout_adjustments", ["ix_payout_adjustments_payout_id", "ix_payout_adjustments_id"]),
        ("payouts", ["ix_payouts_agent_id", "ix_payouts_id"]),
        ("bank_accounts", ["ix_bank_accounts_agent_id", "ix_bank_accounts_id"]),
        ("earnings", ["ix_earnings_task_id", "ix_earnings_agent_id", "ix_earnings_id"]),
        ("commission_rules", ["ix_commission_rules_role_tier", "ix_commission_rules_id"]),
        ("dispute_resolutions", ["ix_dispute_resolutions_dispute_id", "ix_dispute_resolutions_id"]),
        ("disputes", ["ix_disputes_verification_id", "ix_disputes_id"]),
        ("tier_upgrades", ["ix_tier_upgrades_verification_id", "ix_tier_upgrades_id"]),
        ("recheck_requests", ["ix_recheck_requests_verification_id", "ix_recheck_requests_id"]),
        ("share_recipients", ["ix_share_recipients_link_id", "ix_share_recipients_id"]),
        ("share_links", ["ix_share_links_verification_id", "ix_share_links_token", "ix_share_links_id"]),
    ]:
        for idx in idxs:
            op.drop_index(idx, table_name=tbl)
        op.drop_table(tbl)
