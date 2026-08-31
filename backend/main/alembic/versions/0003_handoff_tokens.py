"""handoff_tokens — single-use ledger for WhatsApp handoff links.

The handoff token itself is stateless (a signed RS256 JWT, PRD §7.5). This table is what
makes it **single-use**: redemption claims the token's `jti` here, and the unique
constraint is the enforcement mechanism rather than bookkeeping — two concurrent
redemptions of a forwarded link race on it and exactly one wins.

Revision ID: 0003_handoff_tokens
Revises: 0002_whatsapp_channel
Create Date: 2026-09-01 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.alembic.utils import AlembicUtils
from main.appodus_utils.db.models import UTCDateTime

# revision identifiers, used by Alembic.
revision: str = "0003_handoff_tokens"
down_revision: Union[str, None] = "0002_whatsapp_channel"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_handoff_token_redemptions() -> None:
    op.create_table(
        "handoff_token_redemptions",
        sa.Column("jti", sa.String(length=64), nullable=False),
        sa.Column("intent", sa.String(length=10), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("customer_id", sa.String(length=36), nullable=True),
        sa.Column("redeemed_at", UTCDateTime, nullable=False),
        # Which client actually burned the link — the §7.11 pen-check trail.
        sa.Column("redeemed_ip", sa.String(length=45), nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index(
        "ix_handoff_token_redemptions_id", "handoff_token_redemptions", ["id"], unique=True
    )
    # Single-use enforcement: a replayed nonce collides here.
    op.create_unique_constraint(
        "uq_handoff_token_redemptions_jti", "handoff_token_redemptions", ["jti"]
    )


def upgrade() -> None:
    _create_handoff_token_redemptions()


def downgrade() -> None:
    op.drop_table("handoff_token_redemptions")
