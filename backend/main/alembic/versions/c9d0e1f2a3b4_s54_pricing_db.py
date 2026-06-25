"""S54 -- pricing_tier_configs, pricing_line_items, pricing_upgrade_deltas tables.
Seeds rows from the static TIER_MATRIX so pricing works immediately.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-05-14 00:01:00.000000
"""
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.alembic.utils import AlembicUtils
from main.appodus_utils import Utils

revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NOW = datetime.now(timezone.utc).replace(tzinfo=None)


def _uid() -> str:
    return str(Utils.generate_uuid())


def upgrade() -> None:
    # ── pricing_tier_configs ──────────────────────────────────────
    op.create_table(
        "pricing_tier_configs",
        sa.Column("tier", sa.String(16), nullable=False),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default="NGN"),
        sa.Column("service_fee_minor", sa.BigInteger, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
        *AlembicUtils.base_audit_columns(),
        sa.UniqueConstraint("tier", "currency", name="uq_pricing_tier_currency"),
    )
    op.create_index("ix_pricing_tier_configs_id", "pricing_tier_configs", ["id"], unique=True)
    op.create_index("ix_pricing_tier_configs_tier", "pricing_tier_configs", ["tier"])

    # ── pricing_line_items ────────────────────────────────────────
    op.create_table(
        "pricing_line_items",
        sa.Column("tier_config_id", sa.String(36), nullable=False),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("amount_minor", sa.BigInteger, nullable=False),
        sa.Column("description", sa.String(512), nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_pricing_line_items_id", "pricing_line_items", ["id"], unique=True)
    op.create_index("ix_pricing_line_items_tier_config_id", "pricing_line_items", ["tier_config_id"])

    # ── pricing_upgrade_deltas ────────────────────────────────────
    op.create_table(
        "pricing_upgrade_deltas",
        sa.Column("from_tier", sa.String(16), nullable=False),
        sa.Column("to_tier", sa.String(16), nullable=False),
        sa.Column("delta_minor", sa.BigInteger, nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default="NGN"),
        *AlembicUtils.base_audit_columns(),
        sa.UniqueConstraint("from_tier", "to_tier", "currency", name="uq_pricing_upgrade_delta"),
    )
    op.create_index("ix_pricing_upgrade_deltas_id", "pricing_upgrade_deltas", ["id"], unique=True)

    # ── Seed from static TIER_MATRIX ────────────────────────────
    pricing_tier_configs = sa.table(
        "pricing_tier_configs",
        sa.column("id"), sa.column("tier"), sa.column("label"), sa.column("currency"),
        sa.column("service_fee_minor"), sa.column("is_active"), sa.column("updated_by"),
        sa.column("date_created"), sa.column("date_updated"), sa.column("deleted"), sa.column("version"),
    )
    pricing_line_items = sa.table(
        "pricing_line_items",
        sa.column("id"), sa.column("tier_config_id"), sa.column("label"),
        sa.column("amount_minor"), sa.column("description"), sa.column("sort_order"),
        sa.column("date_created"), sa.column("date_updated"), sa.column("deleted"), sa.column("version"),
    )

    tiers = [
        {
            "id": _uid(), "tier": "BASIC", "label": "Basic verification (registry-only)",
            "currency": "NGN", "service_fee_minor": 1500000, "is_active": True,
            "updated_by": None, "date_created": _NOW, "date_updated": None, "deleted": False, "version": 1,
            "line_items": [
                {"label": "Registry search", "amount_minor": 13000000,
                 "description": "Title search at the registry of record", "sort_order": 0},
                {"label": "Document collection", "amount_minor": 500000,
                 "description": "Acquisition of certified true copies", "sort_order": 1},
            ],
        },
        {
            "id": _uid(), "tier": "STANDARD", "label": "Standard verification (registry + field + survey)",
            "currency": "NGN", "service_fee_minor": 2500000, "is_active": True,
            "updated_by": None, "date_created": _NOW, "date_updated": None, "deleted": False, "version": 1,
            "line_items": [
                {"label": "Registry search", "amount_minor": 13000000,
                 "description": "Title search at the registry of record", "sort_order": 0},
                {"label": "Document collection", "amount_minor": 500000,
                 "description": "Acquisition of certified true copies", "sort_order": 1},
                {"label": "Field inspection", "amount_minor": 9000000,
                 "description": "On-site inspection by Field Agent", "sort_order": 2},
                {"label": "Survey assessment", "amount_minor": 10000000, "description": "Boundary + survey-plan check",
                 "sort_order": 3},
            ],
        },
        {
            "id": _uid(), "tier": "PREMIUM", "label": "Premium verification (full + legal opinion)",
            "currency": "NGN", "service_fee_minor": 5000000, "is_active": True,
            "updated_by": None, "date_created": _NOW, "date_updated": None, "deleted": False, "version": 1,
            "line_items": [
                {"label": "Registry search", "amount_minor": 13000000,
                 "description": "Title search at the registry of record", "sort_order": 0},
                {"label": "Document collection", "amount_minor": 500000,
                 "description": "Acquisition of certified true copies", "sort_order": 1},
                {"label": "Field inspection", "amount_minor": 9000000,
                 "description": "On-site inspection by Field Agent", "sort_order": 2},
                {"label": "Survey assessment", "amount_minor": 12000000, "description": "Boundary + survey-plan check",
                 "sort_order": 3},
                {"label": "Legal opinion", "amount_minor": 35500000,
                 "description": "Structured legal opinion by registered lawyer", "sort_order": 4},
            ],
        },
    ]

    for t in tiers:
        config_id = t["id"]
        line_items_data = t.pop("line_items")
        op.bulk_insert(pricing_tier_configs, [t])
        op.bulk_insert(
            pricing_line_items,
            [
                {
                    "id": _uid(),
                    "tier_config_id": config_id,
                    "label": li["label"],
                    "amount_minor": li["amount_minor"],
                    "description": li["description"],
                    "sort_order": li["sort_order"],
                    "date_created": _NOW,
                    "date_updated": None,
                    "deleted": False,
                    "version": 1,
                }
                for li in line_items_data
            ],
        )


def downgrade() -> None:
    op.drop_table("pricing_upgrade_deltas")
    op.drop_table("pricing_line_items")
    op.drop_table("pricing_tier_configs")
