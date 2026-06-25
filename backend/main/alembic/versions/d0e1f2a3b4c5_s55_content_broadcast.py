"""S55 -- content_items and broadcasts tables.
Seeds published HOW_IT_WORKS_STEP and TESTIMONIAL rows from home.data.ts values.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-05-14 00:02:00.000000
"""
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.alembic.utils import AlembicUtils
from main.appodus_utils import Utils
from main.appodus_utils.db.models import UTCDateTime

revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NOW = datetime.now(timezone.utc).replace(tzinfo=None)


def _uid() -> str:
    return str(Utils.generate_uuid())


def upgrade() -> None:
    # ── content_items ─────────────────────────────────────────────
    op.create_table(
        "content_items",
        sa.Column("item_type", sa.String(32), nullable=False),
        sa.Column("slug", sa.String(128), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("details", sa.Text, nullable=True),
        sa.Column("is_published", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("author_id", sa.String(36), nullable=True),
        sa.Column("lga", sa.String(128), nullable=True),
        sa.Column("state", sa.String(128), nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_content_items_id", "content_items", ["id"], unique=True)
    op.create_index("ix_content_items_item_type", "content_items", ["item_type"])
    op.create_index("ix_content_items_slug", "content_items", ["slug"])
    op.create_index("ix_content_items_type_published", "content_items", ["item_type", "is_published"])

    # ── broadcasts ────────────────────────────────────────────────
    op.create_table(
        "broadcasts",
        sa.Column("subject", sa.String(256), nullable=False),
        sa.Column("body_text", sa.Text, nullable=False),
        sa.Column("body_html", sa.Text, nullable=True),
        sa.Column("audience", sa.String(16), nullable=False, server_default="ALL"),
        sa.Column("channels", sa.Text, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="DRAFT"),
        sa.Column("scheduled_at", UTCDateTime, nullable=True),
        sa.Column("sent_at", UTCDateTime, nullable=True),
        sa.Column("total_recipients", sa.Integer, nullable=True),
        sa.Column("sent_count", sa.Integer, nullable=True, server_default="0"),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_broadcasts_id", "broadcasts", ["id"], unique=True)
    op.create_index("ix_broadcasts_status", "broadcasts", ["status"])

    # ── Seed content_items from home.data.ts ─────────────────────
    content_items = sa.table(
        "content_items",
        sa.column("id"), sa.column("item_type"), sa.column("slug"), sa.column("title"),
        sa.column("body"), sa.column("details"), sa.column("is_published"), sa.column("sort_order"),
        sa.column("author_id"), sa.column("lga"), sa.column("state"),
        sa.column("date_created"), sa.column("date_updated"), sa.column("deleted"), sa.column("version"),
    )

    how_it_works = [
        {
            "id": _uid(), "item_type": "HOW_IT_WORKS_STEP", "sort_order": 0,
            "slug": "hiw-step-1-submit-details", "title": "Submit Details",
            "body": "Provide property coordinates, upload documents, and select your verification tier.",
            "details": None, "is_published": True, "author_id": None, "lga": None, "state": None,
            "date_created": _NOW, "date_updated": None, "deleted": False, "version": 1,
        },
        {
            "id": _uid(), "item_type": "HOW_IT_WORKS_STEP", "sort_order": 1,
            "slug": "hiw-step-2-cross-check-records", "title": "Cross-Check Records",
            "body": "We validate ownership against official registry and survey records with certified agents.",
            "details": None, "is_published": True, "author_id": None, "lga": None, "state": None,
            "date_created": _NOW, "date_updated": None, "deleted": False, "version": 1,
        },
        {
            "id": _uid(), "item_type": "HOW_IT_WORKS_STEP", "sort_order": 2,
            "slug": "hiw-step-3-check-encumbrances", "title": "Check Encumbrances",
            "body": "Identify liens, caveats, pending litigations, or any outstanding claims on the property.",
            "details": None, "is_published": True, "author_id": None, "lga": None, "state": None,
            "date_created": _NOW, "date_updated": None, "deleted": False, "version": 1,
        },
        {
            "id": _uid(), "item_type": "HOW_IT_WORKS_STEP", "sort_order": 3,
            "slug": "hiw-step-4-run-risk-analysis", "title": "Run Risk Analysis",
            "body": "Assessment of area zoning, title history, fraud indicators, and surrounding property context.",
            "details": None, "is_published": True, "author_id": None, "lga": None, "state": None,
            "date_created": _NOW, "date_updated": None, "deleted": False, "version": 1,
        },
        {
            "id": _uid(), "item_type": "HOW_IT_WORKS_STEP", "sort_order": 4,
            "slug": "hiw-step-5-get-certified-report", "title": "Get Certified Report",
            "body": "Receive your high-authority digital report with Trust Score, Verification ID, and agent sign-offs.",
            "details": None, "is_published": True, "author_id": None, "lga": None, "state": None,
            "date_created": _NOW, "date_updated": None, "deleted": False, "version": 1,
        },
    ]

    testimonials = [
        {
            "id": _uid(), "item_type": "TESTIMONIAL", "sort_order": 0,
            "slug": "testimonial-emeka-okafor",
            "title": "Emeka Okafor — London, UK",
            "body": "I was about to wire £65,000 for a property in Lekki. Veriprops found three competing ownership claims before I paid a penny. This service saved my family's financial future.",
            "details": '{"tier":"Premium","initials":"EO"}',
            "is_published": True, "author_id": None, "lga": None, "state": None,
            "date_created": _NOW, "date_updated": None, "deleted": False, "version": 1,
        },
        {
            "id": _uid(), "item_type": "TESTIMONIAL", "sort_order": 1,
            "slug": "testimonial-adaeze-williams",
            "title": "Adaeze Williams — Houston, TX",
            "body": "The Standard report was thorough — GPS-stamped photos, boundary survey, full registry search — all delivered within 6 days. Exactly what I needed from 7,000 miles away.",
            "details": '{"tier":"Standard","initials":"AW"}',
            "is_published": True, "author_id": None, "lga": None, "state": None,
            "date_created": _NOW, "date_updated": None, "deleted": False, "version": 1,
        },
        {
            "id": _uid(), "item_type": "TESTIMONIAL", "sort_order": 2,
            "slug": "testimonial-chukwudi-nwosu",
            "title": "Chukwudi Nwosu — Toronto, Canada",
            "body": "The Trust Score concept is genius. I now only consider properties scoring above 80. It has fundamentally changed how I approach Nigerian real estate investment.",
            "details": '{"tier":"Basic","initials":"CN"}',
            "is_published": True, "author_id": None, "lga": None, "state": None,
            "date_created": _NOW, "date_updated": None, "deleted": False, "version": 1,
        },
    ]

    op.bulk_insert(content_items, how_it_works + testimonials)


def downgrade() -> None:
    op.drop_table("broadcasts")
    op.drop_table("content_items")
