"""Add estimated_price fields to properties table.

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-05-16 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("properties", sa.Column("estimated_price_minor", sa.BigInteger(), nullable=True))
    op.add_column("properties", sa.Column("estimated_price_currency", sa.String(3), nullable=True))


def downgrade() -> None:
    op.drop_column("properties", "estimated_price_currency")
    op.drop_column("properties", "estimated_price_minor")
