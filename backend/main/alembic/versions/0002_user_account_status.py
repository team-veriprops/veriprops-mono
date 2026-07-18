"""user_account_status — admin-controlled whole-account suspension (PRD §2.4a).

Adds the ``account_status`` column set to ``users`` so an admin can suspend and
reactivate a user account from the admin Users directory. Raw string literals
by convention (migrations stay decoupled from app enums); values mirror
``AccountStatus`` (``ACTIVE`` / ``SUSPENDED``).

Revision ID: 0002_user_account_status
Revises: 0001_initial_schema
Create Date: 2026-07-16 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.appodus_utils.db.models import UTCDateTime

# revision identifiers, used by Alembic.
revision: str = "0002_user_account_status"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_users_account_status() -> None:
    op.add_column(
        "users",
        sa.Column("account_status", sa.String(length=16), nullable=False, server_default="ACTIVE"),
    )
    op.add_column("users", sa.Column("suspended_at", UTCDateTime, nullable=True))
    op.add_column("users", sa.Column("suspension_reason", sa.String(length=500), nullable=True))
    # Admin user id (36-char str form) — application-enforced reference, no FK.
    op.add_column("users", sa.Column("suspended_by", sa.String(length=36), nullable=True))


def _drop_users_account_status() -> None:
    op.drop_column("users", "suspended_by")
    op.drop_column("users", "suspension_reason")
    op.drop_column("users", "suspended_at")
    op.drop_column("users", "account_status")


def upgrade() -> None:
    _add_users_account_status()


def downgrade() -> None:
    _drop_users_account_status()
