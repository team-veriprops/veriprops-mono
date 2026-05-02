"""phases 3-5: agent_applications, admin_invitations, properties, verifications, payments

Adds:
- agent_applications (Phase 3)
- admin_invitations (Phase 4)
- properties + verifications + payments + payment_attempts (Phase 5)
- Seeds 5 verification consents (VERIFICATION_DISCLAIMER / FINDINGS_OPINION_ACK
  / JURISDICTION_PLATFORM_ONLY / COMMUNICATION_RECORDING / REFUND_POLICY).
- Adds new SecurityEventType strings via free-text column (no enum DDL needed).

Revision ID: b1f2c3d4e5f6
Revises: fdd959a2cfda
Create Date: 2026-05-01 09:30:00.000000
"""
import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect, JSON
from sqlalchemy.ext.mutable import MutableList

# revision identifiers, used by Alembic.
revision: str = "b1f2c3d4e5f6"
down_revision: Union[str, None] = "fdd959a2cfda"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── helpers ────────────────────────────────────────────────────────


def _base_audit_columns():
    return [
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("date_created", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("date_updated", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("deleted", sa.Boolean(), nullable=False),
        sa.Column("date_deleted", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.String(length=36), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
    ]


def _seed_audit_columns(now: datetime) -> dict:
    return {
        "date_created": now,
        "date_updated": None,
        "deleted": False,
        "version": 1,
    }


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    return name in sa_inspect(bind).get_table_names()


# ── agent_applications ────────────────────────────────────────────


def _create_agent_applications():
    op.create_table(
        "agent_applications",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="DRAFT"),
        sa.Column("types", MutableList.as_mutable(JSON), nullable=False),
        sa.Column("kyc_method", sa.String(length=16), nullable=True),
        sa.Column("bvn_last4", sa.String(length=4), nullable=True),
        sa.Column("bvn_verification_id", sa.String(length=128), nullable=True),
        sa.Column("bvn_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id_doc_type", sa.String(length=32), nullable=True),
        sa.Column("id_doc_url", sa.String(length=512), nullable=True),
        sa.Column("selfie_url", sa.String(length=512), nullable=True),
        sa.Column("selfie_match_score", sa.Integer(), nullable=True),
        sa.Column("selfie_matched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("surveyor_licence_no", sa.String(length=64), nullable=True),
        sa.Column("surveyor_licence_url", sa.String(length=512), nullable=True),
        sa.Column("nba_licence_no", sa.String(length=64), nullable=True),
        sa.Column("nba_licence_url", sa.String(length=512), nullable=True),
        sa.Column("years_of_experience", sa.Integer(), nullable=True),
        sa.Column("coverage_states", MutableList.as_mutable(JSON), nullable=False),
        sa.Column("coverage_lgas", MutableList.as_mutable(JSON), nullable=False),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("truthfulness_acknowledged", sa.String(length=8), nullable=True),
        sa.Column("agent_terms_consent_id", sa.String(length=36), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by_admin_id", sa.String(length=36), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        *_base_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_agent_applications_user"),
    )
    op.create_index("ix_agent_applications_user_id", "agent_applications", ["user_id"], unique=False)
    op.create_index("ix_agent_applications_status", "agent_applications", ["status"], unique=False)
    op.create_index(
        "ix_agent_applications_status_submitted",
        "agent_applications",
        ["status", "submitted_at"],
        unique=False,
    )


def _drop_agent_applications():
    op.drop_index("ix_agent_applications_status_submitted", table_name="agent_applications")
    op.drop_index("ix_agent_applications_status", table_name="agent_applications")
    op.drop_index("ix_agent_applications_user_id", table_name="agent_applications")
    op.drop_constraint("uq_agent_applications_user", "agent_applications", type_="unique")
    op.drop_table("agent_applications")


# ── admin_invitations ─────────────────────────────────────────────


def _create_admin_invitations():
    op.create_table(
        "admin_invitations",
        sa.Column("email_normalized", sa.String(length=254), nullable=False),
        sa.Column("sub_role", sa.String(length=16), nullable=False),
        sa.Column("inviter_admin_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_by_user_id", sa.String(length=36), nullable=True),
        *_base_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_admin_invitations_token"),
    )
    op.create_index("ix_admin_invitations_email", "admin_invitations", ["email_normalized"], unique=False)
    op.create_index("ix_admin_invitations_status", "admin_invitations", ["status"], unique=False)


def _drop_admin_invitations():
    op.drop_index("ix_admin_invitations_status", table_name="admin_invitations")
    op.drop_index("ix_admin_invitations_email", table_name="admin_invitations")
    op.drop_constraint("uq_admin_invitations_token", "admin_invitations", type_="unique")
    op.drop_table("admin_invitations")


# ── properties ────────────────────────────────────────────────────


def _create_properties():
    op.create_table(
        "properties",
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=True),
        sa.Column("parsed_listing_data", sa.Text(), nullable=True),
        sa.Column("property_type", sa.String(length=16), nullable=False),
        sa.Column("state", sa.String(length=64), nullable=False),
        sa.Column("lga", sa.String(length=128), nullable=True),
        sa.Column("address_line", sa.String(length=512), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.Column("landmark_description", sa.Text(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("documents", MutableList.as_mutable(JSON), nullable=False),
        sa.Column("seller_info", sa.Text(), nullable=True),
        *_base_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_properties_state_lga", "properties", ["state", "lga"], unique=False)


def _drop_properties():
    op.drop_index("ix_properties_state_lga", table_name="properties")
    op.drop_table("properties")


# ── verifications ─────────────────────────────────────────────────


def _create_verifications():
    op.create_table(
        "verifications",
        sa.Column("vid", sa.String(length=24), nullable=False),
        sa.Column("customer_id", sa.String(length=36), nullable=False),
        sa.Column("property_id", sa.String(length=36), nullable=True),
        sa.Column("tier", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("pricing_snapshot", sa.Text(), nullable=True),
        sa.Column("consent_snapshot_id", sa.String(length=36), nullable=True),
        sa.Column("payment_id", sa.String(length=36), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("draft_payload", sa.Text(), nullable=True),
        sa.Column("draft_step", sa.Integer(), nullable=False, server_default=sa.text("0")),
        *_base_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vid", name="uq_verifications_vid"),
    )
    op.create_index("ix_verifications_customer_id", "verifications", ["customer_id"], unique=False)
    op.create_index("ix_verifications_status", "verifications", ["status"], unique=False)


def _drop_verifications():
    op.drop_index("ix_verifications_status", table_name="verifications")
    op.drop_index("ix_verifications_customer_id", table_name="verifications")
    op.drop_constraint("uq_verifications_vid", "verifications", type_="unique")
    op.drop_table("verifications")


# ── payments ──────────────────────────────────────────────────────


def _create_payments():
    op.create_table(
        "payments",
        sa.Column("verification_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("provider_ref", sa.String(length=128), nullable=True),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("wire_proof_url", sa.String(length=512), nullable=True),
        sa.Column("failure_reason", sa.String(length=512), nullable=True),
        sa.Column("confirmed_by_admin_id", sa.String(length=36), nullable=True),
        sa.Column("provider_metadata", sa.Text(), nullable=True),
        *_base_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payments_verification", "payments", ["verification_id"], unique=False)
    op.create_index("ix_payments_status", "payments", ["status"], unique=False)
    op.create_index("ix_payments_provider_ref", "payments", ["provider_ref"], unique=False)


def _drop_payments():
    op.drop_index("ix_payments_provider_ref", table_name="payments")
    op.drop_index("ix_payments_status", table_name="payments")
    op.drop_index("ix_payments_verification", table_name="payments")
    op.drop_table("payments")


def _create_payment_attempts():
    op.create_table(
        "payment_attempts",
        sa.Column("payment_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("provider_ref", sa.String(length=128), nullable=True),
        sa.Column("failure_reason", sa.String(length=512), nullable=True),
        sa.Column("event_payload", sa.Text(), nullable=True),
        *_base_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payment_attempts_payment", "payment_attempts", ["payment_id"], unique=False)


def _drop_payment_attempts():
    op.drop_index("ix_payment_attempts_payment", table_name="payment_attempts")
    op.drop_table("payment_attempts")


# ── seed: verification consent docs ───────────────────────────────


VERIFICATION_CONSENT_SEEDS = [
    ("VERIFICATION_DISCLAIMER", "1.0.0", "Verification Disclaimer", "/legal/verification-disclaimer"),
    ("FINDINGS_OPINION_ACK", "1.0.0", "Findings & Opinion Acknowledgement", "/legal/findings-opinion"),
    ("JURISDICTION_PLATFORM_ONLY", "1.0.0", "Jurisdiction & Platform-Only Transactions", "/legal/jurisdiction"),
    ("COMMUNICATION_RECORDING", "1.0.0", "Communication Recording", "/legal/communication-recording"),
    ("REFUND_POLICY", "1.0.0", "Refund & Cancellation Policy", "/legal/refund-policy"),
]
SEED_EFFECTIVE_AT = datetime(2026, 5, 1, tzinfo=timezone.utc)


def _seed_verification_consents() -> None:
    conn = op.get_bind()
    now = datetime.now(timezone.utc)
    for doc_type, ver, title, href in VERIFICATION_CONSENT_SEEDS:
        existing = conn.execute(
            sa.text(
                "SELECT 1 FROM consent_documents "
                "WHERE type = :type AND consent_version = :ver LIMIT 1"
            ),
            {"type": doc_type, "ver": ver},
        ).first()
        if existing:
            continue
        conn.execute(
            sa.text(
                "INSERT INTO consent_documents "
                "(id, type, consent_version, effective_at, title, href, "
                " date_created, deleted, version) "
                "VALUES (:id, :type, :ver, :eff, :title, :href, :now, FALSE, 1)"
            ),
            {
                "id": str(uuid.uuid4()),
                "type": doc_type,
                "ver": ver,
                "eff": SEED_EFFECTIVE_AT,
                "title": title,
                "href": href,
                "now": now,
            },
        )


# ── upgrade / downgrade ───────────────────────────────────────────


def upgrade() -> None:
    if not _table_exists("agent_applications"):
        _create_agent_applications()
    if not _table_exists("admin_invitations"):
        _create_admin_invitations()
    if not _table_exists("properties"):
        _create_properties()
    if not _table_exists("verifications"):
        _create_verifications()
    if not _table_exists("payments"):
        _create_payments()
    if not _table_exists("payment_attempts"):
        _create_payment_attempts()
    _seed_verification_consents()


def downgrade() -> None:
    if _table_exists("payment_attempts"):
        _drop_payment_attempts()
    if _table_exists("payments"):
        _drop_payments()
    if _table_exists("verifications"):
        _drop_verifications()
    if _table_exists("properties"):
        _drop_properties()
    if _table_exists("admin_invitations"):
        _drop_admin_invitations()
    if _table_exists("agent_applications"):
        _drop_agent_applications()
