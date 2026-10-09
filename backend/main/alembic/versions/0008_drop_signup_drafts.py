"""drop signup_drafts — a half-finished signup resumes from the browser alone (§7.1).

The server-side draft was keyed on an email before any account existed, so anyone who typed
that email could read it back — and its payload held the password in plain text. Dropping the
table purges every such row; the signup wizard keeps a password-free draft in localStorage.

The downgrade recreates the table empty: the rows it held must never come back.

Revision ID: 0008_drop_signup_drafts
Revises: 0007_refund_requests
Create Date: 2026-10-01 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.alembic.utils import AlembicUtils
from main.appodus_utils.db.models import UTCDateTime

revision: str = "0008_drop_signup_drafts"
down_revision: Union[str, None] = "0007_refund_requests"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "signup_drafts"


def upgrade() -> None:
    op.drop_table(_TABLE)


def downgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("expires_at", UTCDateTime, nullable=False),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_signup_drafts_id", _TABLE, ["id"], unique=True)
    op.create_index("ix_signup_drafts_email", _TABLE, ["email"], unique=False)
    op.create_index("ix_signup_drafts_expires_at", _TABLE, ["expires_at"], unique=False)
    op.create_index(
        "uq_signup_drafts_email", _TABLE, ["email"], unique=True,
        postgresql_where=sa.text("deleted = false"),
    )
    op.create_index("ix_signup_drafts_email_active", _TABLE, ["email", "expires_at"], unique=False)
