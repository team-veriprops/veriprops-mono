"""widen_truthfulness_acknowledged

Revision ID: add0e51b777f
Revises: f2a3b4c5d6e7
Create Date: 2026-05-18 15:56:04.024189

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add0e51b777f'
down_revision: Union[str, None] = 'f2a3b4c5d6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "agent_applications",
        "truthfulness_acknowledged",
        type_=sa.String(16),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "agent_applications",
        "truthfulness_acknowledged",
        type_=sa.String(8),
        existing_nullable=True,
    )
