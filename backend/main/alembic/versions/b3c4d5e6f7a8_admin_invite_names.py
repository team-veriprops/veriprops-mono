"""Add first_name and last_name to admin_invitations.

Revision ID: b3c4d5e6f7a8
Revises: a7b8c9d0e1f2
Create Date: 2026-05-13 10:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("admin_invitations", sa.Column("first_name", sa.String(100), nullable=True))
    op.add_column("admin_invitations", sa.Column("last_name", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("admin_invitations", "last_name")
    op.drop_column("admin_invitations", "first_name")
