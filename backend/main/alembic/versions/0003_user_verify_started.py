"""user_verify_started — first-login new-verification auto-launch gate.

Adds ``has_started_verification`` to ``users``: flipped true the moment a
customer dirties their first verification draft, so the frontend only ever
auto-launches the new-verification wizard on a login before that first start
(post-signup and any later standalone login alike).

Revision ID: 0003_user_verify_started
Revises: 0002_user_account_status
Create Date: 2026-07-18 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_user_verify_started"
down_revision: Union[str, None] = "0002_user_account_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_users_has_started_verification() -> None:
    op.add_column(
        "users",
        sa.Column("has_started_verification", sa.Boolean(), nullable=False, server_default="false"),
    )


def _drop_users_has_started_verification() -> None:
    op.drop_column("users", "has_started_verification")


def upgrade() -> None:
    _add_users_has_started_verification()


def downgrade() -> None:
    _drop_users_has_started_verification()
