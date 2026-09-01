"""whatsapp_templates — Meta's verdict on each §7.7 template.

Additive, per decision D49 (`0001_initial_schema` is frozen).

Stores only what Meta owns: review status, its own id for the template, and a rejection
reason. The template *definitions* — name, category, language, ordered parameters — are
code-owned (D59a), because the code is what fills those parameters; a row that could
disagree with the sender would describe something the app does not do.

No rows are seeded. A declared template with no row reads as `NOT_FOUND`, which is the
honest state before anything has been submitted to Meta — and precisely what the §7.11
launch gate is asking about.

Revision ID: 0005_whatsapp_templates
Revises: 0004_whatsapp_linking
Create Date: 2026-09-01 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.alembic.utils import AlembicUtils
from main.appodus_utils.db.models import UTCDateTime

# revision identifiers, used by Alembic.
revision: str = "0005_whatsapp_templates"
down_revision: Union[str, None] = "0004_whatsapp_linking"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Raw strings by design — migrations stay decoupled from app enums.
_STATUS_NOT_FOUND = "NOT_FOUND"


def _create_whatsapp_templates() -> None:
    op.create_table(
        "whatsapp_templates",
        # Also the AvailableTemplate slug and the Jinja filename, which is what keeps the
        # declaration, the body copy, this row, and the wire from drifting apart.
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("language", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=_STATUS_NOT_FOUND),
        sa.Column("remote_id", sa.String(length=64), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("last_synced_at", UTCDateTime, nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_whatsapp_templates_id", "whatsapp_templates", ["id"], unique=True)
    # One row per Meta template name — a second row would let two syncs disagree.
    op.create_unique_constraint("uq_whatsapp_templates_name", "whatsapp_templates", ["name"])


def upgrade() -> None:
    _create_whatsapp_templates()


def downgrade() -> None:
    op.drop_table("whatsapp_templates")
