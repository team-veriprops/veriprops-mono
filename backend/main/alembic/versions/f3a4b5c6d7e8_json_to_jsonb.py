"""Convert JSON columns to JSONB (PostgreSQL only).

Part of the MySQL → PostgreSQL migration. The ORM now declares these columns
with ``JSONB_VARIANT`` (``JSON().with_variant(JSONB(), "postgresql")``), so on
PostgreSQL they should be stored as ``jsonb`` — indexable and able to use the
``@>`` containment operator (see analytics ``conversion_funnel``).

This migration is **dialect-guarded**: it only runs on PostgreSQL. On any other
dialect (MySQL/SQLite) it is a no-op, preserving the dual-DB abstraction in
``settings.SupportedDB``. Each column is converted only if its table exists, so
the migration is safe to run against partially-built databases.

Revision ID: f3a4b5c6d7e8
Revises: add0e51b777f
Create Date: 2026-05-31 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect as sa_inspect

revision: str = "f3a4b5c6d7e8"
down_revision: Union[str, None] = "add0e51b777f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (table, column) pairs whose ORM type is JSONB_VARIANT.
_JSON_COLUMNS: list[tuple[str, str]] = [
    ("users", "personas"),
    ("agent_applications", "types"),
    ("agent_applications", "coverage_states"),
    ("agent_applications", "coverage_lgas"),
    ("kyc_records", "webhook_payload"),
    ("devices", "push_token"),
    ("properties", "documents"),
    ("verification_notes", "tags"),
    ("evidence_items", "details"),
    ("audit_logs", "details"),
    ("messages", "to"),
    ("messages", "payload"),
    ("messages", "extras"),
]


def _convert(target_type: str) -> None:
    """Alter every known JSON column to ``target_type`` on PostgreSQL only."""
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    inspector = sa_inspect(bind)
    existing_tables = set(inspector.get_table_names())

    for table, column in _JSON_COLUMNS:
        if table not in existing_tables:
            continue
        column_names = {c["name"] for c in inspector.get_columns(table)}
        if column not in column_names:
            continue
        # Quote the identifier (e.g. reserved word "to") in the USING clause.
        op.execute(
            f'ALTER TABLE "{table}" '
            f'ALTER COLUMN "{column}" TYPE {target_type} '
            f'USING "{column}"::{target_type}'
        )


def upgrade() -> None:
    _convert("jsonb")


def downgrade() -> None:
    _convert("json")
