"""S30 — trust_score_weight_config (seeded), trust_score_breakdowns, verifications.trust_score.

Revision ID: a1b2c3d4e5f6
Revises: f5a6b7c8d9e0
Create Date: 2026-05-11 00:00:02.000000
"""
from typing import Sequence, Union
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

from main.appodus_utils.db.models import UTCDateTime

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f5a6b7c8d9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Provisional defaults (D2 decision)
_SEED_WEIGHTS = [
    ("BASIC",    "REGISTRY",  "100.000"),
    ("STANDARD", "FIELD",      "35.000"),
    ("STANDARD", "SURVEYOR",   "30.000"),
    ("STANDARD", "REGISTRY",   "35.000"),
    ("PREMIUM",  "FIELD",      "25.000"),
    ("PREMIUM",  "SURVEYOR",   "20.000"),
    ("PREMIUM",  "REGISTRY",   "30.000"),
    ("PREMIUM",  "LAWYER",     "25.000"),
]


def upgrade() -> None:
    # ── trust_score_weight_config ──────────────────────────────────────────────
    op.create_table(
        "trust_score_weight_config",
        sa.Column("id", sa.String(36), nullable=False, primary_key=True),
        sa.Column("date_created", UTCDateTime, nullable=False),
        sa.Column("date_updated", UTCDateTime, nullable=True),
        sa.Column("date_deleted", UTCDateTime, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, default=1),
        sa.Column("deleted", sa.Boolean, nullable=False, default=False),
        sa.Column("tier", sa.String(16), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("weight", sa.Numeric(6, 3), nullable=False, default=0),
        sa.Column("updated_by", sa.String(36), nullable=True),
        sa.UniqueConstraint("tier", "role", name="uq_ts_weight_tier_role"),
    )
    op.create_index("ix_ts_weight_config_id", "trust_score_weight_config", ["id"], unique=True)
    op.create_index("ix_ts_weight_config_tier", "trust_score_weight_config", ["tier"])

    # Seed default weights
    now = datetime.now(timezone.utc)
    weight_table = sa.table(
        "trust_score_weight_config",
        sa.column("id", sa.String),
        sa.column("date_created", UTCDateTime),
        sa.column("version", sa.Integer),
        sa.column("deleted", sa.Boolean),
        sa.column("tier", sa.String),
        sa.column("role", sa.String),
        sa.column("weight", sa.Numeric),
    )
    op.bulk_insert(weight_table, [
        {"id": str(uuid.uuid4()), "date_created": now, "version": 1, "deleted": False,
         "tier": tier, "role": role, "weight": weight}
        for tier, role, weight in _SEED_WEIGHTS
    ])

    # ── trust_score_breakdowns ─────────────────────────────────────────────────
    op.create_table(
        "trust_score_breakdowns",
        sa.Column("id", sa.String(36), nullable=False, primary_key=True),
        sa.Column("date_created", UTCDateTime, nullable=False),
        sa.Column("date_updated", UTCDateTime, nullable=True),
        sa.Column("date_deleted", UTCDateTime, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, default=1),
        sa.Column("deleted", sa.Boolean, nullable=False, default=False),
        sa.Column("verification_id", sa.String(36), nullable=False),
        sa.Column("task_scores_json", sa.Text, nullable=False),
        sa.Column("weights_json", sa.Text, nullable=False),
        sa.Column("computed_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("computed_at", UTCDateTime, nullable=False),
    )
    op.create_index("ix_ts_breakdowns_id", "trust_score_breakdowns", ["id"], unique=True)
    op.create_index("ix_ts_breakdowns_verification_id", "trust_score_breakdowns", ["verification_id"])

    # ── verifications.trust_score column ──────────────────────────────────────
    op.add_column("verifications", sa.Column("trust_score", sa.Numeric(5, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("verifications", "trust_score")
    op.drop_index("ix_ts_breakdowns_verification_id", table_name="trust_score_breakdowns")
    op.drop_index("ix_ts_breakdowns_id", table_name="trust_score_breakdowns")
    op.drop_table("trust_score_breakdowns")
    op.drop_index("ix_ts_weight_config_tier", table_name="trust_score_weight_config")
    op.drop_index("ix_ts_weight_config_id", table_name="trust_score_weight_config")
    op.drop_table("trust_score_weight_config")
