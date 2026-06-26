"""initial_schema — full Veriprops schema in one migration.

This single migration is a squash of the original 20-file chain
(fdd959a2cfda … f3a4b5c6d7e8). Every table is created once in its final
shape: later add_column / alter_column steps are folded into the relevant
CREATE TABLE, and JSON columns are declared with ``JSONB_VARIANT`` so the
former Postgres-only JSON→JSONB pass is unnecessary.

Each table lives in its own ``_create_<table>()`` helper (mirroring the
original auto_generated migration) and reuses ``AlembicUtils`` helpers.
Seed data (consent documents, super admin, trust-score weights, pricing,
content) is preserved effect-for-effect.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-06-26 00:00:00.000000
"""
import json
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.alembic.utils import AlembicUtils
from main.app.config.settings import settings
from main.appodus_utils import Utils
from main.appodus_utils.db.models import UTCDateTime, JSONB_VARIANT

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ─────────────────────────────────────────────────────────────────────
# Core / auth tables (orig: fdd959a2cfda)
# ─────────────────────────────────────────────────────────────────────


def _create_users():
    op.create_table(
        "users",
        sa.Column("first_name", sa.String(length=60), nullable=False),
        sa.Column("last_name", sa.String(length=60), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("email_normalized", sa.String(length=254), nullable=False),
        sa.Column("email_verified", sa.Boolean(), nullable=False),
        sa.Column("phone_country_code", sa.String(length=2), nullable=False),
        sa.Column("phone_dial_code", sa.String(length=8), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("phone_e164", sa.String(length=32), nullable=True),
        sa.Column("phone_verified", sa.Boolean(), nullable=False),
        sa.Column("country_of_residence", sa.String(length=2), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("preferred_currency", sa.String(length=8), nullable=False),
        sa.Column("user_type", sa.String(length=8), nullable=False),
        sa.Column("personas", JSONB_VARIANT, nullable=False),
        sa.Column("admin_sub_role", sa.String(length=16), nullable=True),
        sa.Column("trust_status", sa.String(length=16), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("avatar_url", sa.String(length=512), nullable=True),
        sa.Column("locked_until", UTCDateTime, nullable=True),
        sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"),
        # folded from a7b8c9d0e1f2 (S51-S52)
        sa.Column("credit_balance_kobo", sa.BigInteger(), nullable=False, server_default="0"),
        *AlembicUtils.base_audit_columns(),
        sa.UniqueConstraint("email_normalized", name="uq_users_email"),
    )
    op.create_index("ix_users_phone_e164", "users", ["phone_e164"], unique=False)
    op.create_index("ix_users_deleted", "users", ["deleted"], unique=False)
    op.create_index("ix_users_id", "users", ["id"], unique=True)


def _create_key_values():
    op.create_table(
        "key_values",
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value", sa.LargeBinary(), nullable=False),
        sa.Column("expires_at", UTCDateTime, nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_index(op.f("ix_key_values_key"), "key_values", ["key"], unique=True)


def _create_oauth_identities():
    op.create_table(
        "oauth_identities",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("raw_profile", sa.Text(), nullable=True),
        *AlembicUtils.base_audit_columns(),
        sa.UniqueConstraint("provider", "subject", name="uq_oauth_provider_subject"),
    )
    op.create_index("ix_oauth_identities_id", "oauth_identities", ["id"], unique=True)
    op.create_index("ix_oauth_identities_user_id", "oauth_identities", ["user_id"], unique=False)


def _create_consent_documents():
    op.create_table(
        "consent_documents",
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("consent_version", sa.String(length=16), nullable=False),
        sa.Column("effective_at", UTCDateTime, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("href", sa.String(length=255), nullable=False),
        *AlembicUtils.base_audit_columns(),
        sa.UniqueConstraint("type", "consent_version", name="uq_consent_type_version"),
    )
    op.create_index("ix_consent_documents_type", "consent_documents", ["type"], unique=False)
    op.create_index("ix_consent_active_lookup", "consent_documents", ["type", "effective_at"], unique=False)
    op.create_index("ix_consent_documents_id", "consent_documents", ["id"], unique=True)


def _create_user_consents():
    op.create_table(
        "user_consents",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("document_type", sa.String(length=32), nullable=False),
        sa.Column("consent_version", sa.String(length=16), nullable=False),
        sa.Column("accepted_at", UTCDateTime, nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("device_fingerprint", sa.String(length=128), nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_user_consents_user_id", "user_consents", ["user_id"], unique=False)
    op.create_index("ix_user_consents_id", "user_consents", ["id"], unique=True)


def _create_device_sessions():
    op.create_table(
        "device_sessions",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=128), nullable=False),
        sa.Column("device", sa.String(length=512), nullable=False),
        sa.Column("browser", sa.String(length=64), nullable=True),
        sa.Column("os", sa.String(length=64), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("approx_location", sa.String(length=128), nullable=True),
        sa.Column("device_fingerprint", sa.String(length=128), nullable=True),
        sa.Column("last_active_at", UTCDateTime, nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.Column("revoked_at", UTCDateTime, nullable=True),
        *AlembicUtils.base_audit_columns(),
        sa.UniqueConstraint("refresh_token_hash", name="uq_device_token_hash"),
    )
    op.create_index("ix_device_sessions_user_id", "device_sessions", ["user_id"], unique=False)
    op.create_index("ix_device_sessions_id", "device_sessions", ["id"], unique=True)


def _create_security_events():
    op.create_table(
        "security_events",
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("approx_location", sa.String(length=128), nullable=True),
        sa.Column("device", sa.String(length=512), nullable=True),
        sa.Column("device_fingerprint", sa.String(length=128), nullable=True),
        sa.Column("occurred_at", UTCDateTime, nullable=False),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_security_events_user_id", "security_events", ["user_id"], unique=False)
    op.create_index("ix_security_events_type", "security_events", ["type"], unique=False)
    op.create_index("ix_security_events_occurred_at", "security_events", ["occurred_at"], unique=False)
    op.create_index("ix_security_events_id", "security_events", ["id"], unique=True)


def _create_password_reset_tokens():
    op.create_table(
        "password_reset_tokens",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", UTCDateTime, nullable=False),
        sa.Column("consumed_at", UTCDateTime, nullable=True),
        *AlembicUtils.base_audit_columns(),
        sa.UniqueConstraint("token_hash", name="uq_password_reset_token_hash"),
    )
    op.create_index("ix_password_reset_user", "password_reset_tokens", ["user_id"], unique=False)
    op.create_index("ix_password_reset_tokens_id", "password_reset_tokens", ["id"], unique=True)


def _create_signup_drafts():
    op.create_table(
        "signup_drafts",
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("expires_at", UTCDateTime, nullable=False),
        *AlembicUtils.base_audit_columns(),
        sa.UniqueConstraint("email", name="uq_signup_drafts_email"),
    )
    op.create_index("ix_signup_drafts_id", "signup_drafts", ["id"], unique=True)
    op.create_index("ix_signup_drafts_email", "signup_drafts", ["email"], unique=False)
    op.create_index("ix_signup_drafts_expires_at", "signup_drafts", ["expires_at"], unique=False)
    op.create_index(
        "ix_signup_drafts_email_active", "signup_drafts", ["email", "expires_at"], unique=False,
    )


def _create_messages():
    op.create_table(
        "messages",
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("to", JSONB_VARIANT, nullable=False),
        sa.Column("payload", JSONB_VARIANT, nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("provider_id", sa.String(length=255), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=True),
        sa.Column("scheduled_at", UTCDateTime, nullable=True),
        sa.Column("sent_at", UTCDateTime, nullable=True),
        sa.Column("delivered_at", UTCDateTime, nullable=True),
        sa.Column("extras", JSONB_VARIANT, nullable=True),
        sa.Column("callback_url", sa.String(length=100), nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index(op.f("ix_messages_deleted"), "messages", ["deleted"], unique=False)
    op.create_index(op.f("ix_messages_id"), "messages", ["id"], unique=True)


# ─────────────────────────────────────────────────────────────────────
# Phases 3-5 (orig: b1f2c3d4e5f6)
# ─────────────────────────────────────────────────────────────────────


def _create_agent_applications():
    op.create_table(
        "agent_applications",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="DRAFT"),
        sa.Column("types", JSONB_VARIANT, nullable=False),
        sa.Column("kyc_method", sa.String(length=16), nullable=True),
        sa.Column("bvn_last4", sa.String(length=4), nullable=True),
        sa.Column("bvn_verification_id", sa.String(length=128), nullable=True),
        sa.Column("bvn_verified_at", UTCDateTime, nullable=True),
        sa.Column("id_doc_type", sa.String(length=32), nullable=True),
        sa.Column("id_doc_url", sa.String(length=512), nullable=True),
        sa.Column("selfie_url", sa.String(length=512), nullable=True),
        sa.Column("selfie_match_score", sa.Integer(), nullable=True),
        sa.Column("selfie_matched_at", UTCDateTime, nullable=True),
        sa.Column("surveyor_licence_no", sa.String(length=64), nullable=True),
        sa.Column("surveyor_licence_url", sa.String(length=512), nullable=True),
        sa.Column("nba_licence_no", sa.String(length=64), nullable=True),
        sa.Column("nba_licence_url", sa.String(length=512), nullable=True),
        sa.Column("years_of_experience", sa.Integer(), nullable=True),
        sa.Column("coverage_states", JSONB_VARIANT, nullable=False),
        sa.Column("coverage_lgas", JSONB_VARIANT, nullable=False),
        sa.Column("bio", sa.Text(), nullable=True),
        # widened from String(8) → String(16) (folded from add0e51b777f)
        sa.Column("truthfulness_acknowledged", sa.String(length=16), nullable=True),
        sa.Column("agent_terms_consent_id", sa.String(length=36), nullable=True),
        sa.Column("submitted_at", UTCDateTime, nullable=True),
        sa.Column("reviewed_by_admin_id", sa.String(length=36), nullable=True),
        sa.Column("reviewed_at", UTCDateTime, nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        # folded from f6a7b8c9d0e1 (S49-S50)
        sa.Column("availability_status", sa.String(length=20), nullable=False, server_default="AVAILABLE"),
        sa.Column("max_travel_km", sa.Integer(), nullable=True),
        *AlembicUtils.base_audit_columns(),
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


def _create_admin_invitations():
    op.create_table(
        "admin_invitations",
        sa.Column("email_normalized", sa.String(length=254), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=True),
        sa.Column("last_name", sa.String(length=100), nullable=True),
        sa.Column("sub_role", sa.String(length=16), nullable=False),
        sa.Column("inviter_admin_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("expires_at", UTCDateTime, nullable=False),
        sa.Column("accepted_at", UTCDateTime, nullable=True),
        sa.Column("accepted_by_user_id", sa.String(length=36), nullable=True),
        *AlembicUtils.base_audit_columns(),
        sa.UniqueConstraint("token_hash", name="uq_admin_invitations_token"),
    )
    op.create_index("ix_admin_invitations_email", "admin_invitations", ["email_normalized"], unique=False)
    op.create_index("ix_admin_invitations_status", "admin_invitations", ["status"], unique=False)


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
        sa.Column("documents", JSONB_VARIANT, nullable=False),
        sa.Column("seller_info", sa.Text(), nullable=True),
        # folded from f2a3b4c5d6e7
        sa.Column("estimated_price_minor", sa.BigInteger(), nullable=True),
        sa.Column("estimated_price_currency", sa.String(length=3), nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_properties_state_lga", "properties", ["state", "lga"], unique=False)


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
        sa.Column("submitted_at", UTCDateTime, nullable=True),
        sa.Column("paid_at", UTCDateTime, nullable=True),
        sa.Column("completed_at", UTCDateTime, nullable=True),
        sa.Column("draft_payload", sa.Text(), nullable=True),
        sa.Column("draft_step", sa.Integer(), nullable=False, server_default=sa.text("0")),
        # folded from a1b2c3d4e5f6 (S30)
        sa.Column("trust_score", sa.Numeric(5, 2), nullable=True),
        # folded from a7b8c9d0e1f2 (S51-S52)
        sa.Column("abandonment_email_sent_at", UTCDateTime, nullable=True),
        *AlembicUtils.base_audit_columns(),
        sa.UniqueConstraint("vid", name="uq_verifications_vid"),
    )
    op.create_index("ix_verifications_customer_id", "verifications", ["customer_id"], unique=False)
    op.create_index("ix_verifications_status", "verifications", ["status"], unique=False)
    # folded analytics indexes from b8c9d0e1f2a3 (S53)
    op.create_index("ix_verifications_status_tier", "verifications", ["status", "tier"])
    op.create_index("ix_verifications_paid_completed", "verifications", ["paid_at", "completed_at"])


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
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_payments_verification", "payments", ["verification_id"], unique=False)
    op.create_index("ix_payments_status", "payments", ["status"], unique=False)
    op.create_index("ix_payments_provider_ref", "payments", ["provider_ref"], unique=False)
    # folded analytics index from b8c9d0e1f2a3 (S53)
    op.create_index("ix_payments_status_amount", "payments", ["status", "amount_minor"])


def _create_payment_attempts():
    op.create_table(
        "payment_attempts",
        sa.Column("payment_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("provider_ref", sa.String(length=128), nullable=True),
        sa.Column("failure_reason", sa.String(length=512), nullable=True),
        sa.Column("event_payload", sa.Text(), nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_payment_attempts_payment", "payment_attempts", ["payment_id"], unique=False)


# ─────────────────────────────────────────────────────────────────────
# Audit logs (orig: c2d3e4f5a6b7)
# ─────────────────────────────────────────────────────────────────────


def _create_audit_logs():
    op.create_table(
        "audit_logs",
        sa.Column("actor_id", sa.String(36), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.String(36), nullable=False),
        sa.Column("from_state", sa.String(32), nullable=True),
        sa.Column("to_state", sa.String(32), nullable=True),
        sa.Column("details", JSONB_VARIANT, nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("occurred_at", UTCDateTime, nullable=False),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_audit_logs_id", "audit_logs", ["id"])
    op.create_index("ix_audit_logs_deleted", "audit_logs", ["deleted"])
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_resource_type", "audit_logs", ["resource_type"])
    op.create_index("ix_audit_logs_resource_id", "audit_logs", ["resource_id"])
    op.create_index("ix_audit_logs_occurred_at", "audit_logs", ["occurred_at"])
    op.create_index("ix_audit_logs_resource", "audit_logs", ["resource_type", "resource_id"])


# ─────────────────────────────────────────────────────────────────────
# KYC records (orig: d3e4f5a6b7c8)
# ─────────────────────────────────────────────────────────────────────


def _create_kyc_records():
    op.create_table(
        "kyc_records",
        sa.Column("application_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("kyc_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_ref", sa.String(128), nullable=True),
        sa.Column("score", sa.Integer, nullable=True),
        sa.Column("failure_reason", sa.Text, nullable=True),
        sa.Column("webhook_payload", JSONB_VARIANT, nullable=True),
        sa.Column("reviewed_by_admin_id", sa.String(36), nullable=True),
        sa.Column("reviewed_at", UTCDateTime, nullable=True),
        sa.Column("admin_decision", sa.String(8), nullable=True),
        sa.Column("admin_notes", sa.Text, nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_kyc_records_application_id", "kyc_records", ["application_id"])
    op.create_index("ix_kyc_records_user_id", "kyc_records", ["user_id"])
    op.create_index("ix_kyc_records_status", "kyc_records", ["status"])
    op.create_index("ix_kyc_records_provider_ref", "kyc_records", ["provider_ref"])
    op.create_index("ix_kyc_records_app_type", "kyc_records", ["application_id", "kyc_type"])


# ─────────────────────────────────────────────────────────────────────
# S18-S27 tables (orig: e4f5a6b7c8d9)
# ─────────────────────────────────────────────────────────────────────


def _create_admin_config():
    op.create_table(
        "admin_config",
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_admin_config_id", "admin_config", ["id"], unique=True)
    op.create_index("ix_admin_config_deleted", "admin_config", ["deleted"])
    op.create_index("ix_admin_config_updated_by", "admin_config", ["updated_by"])
    op.create_unique_constraint("uq_admin_config_key", "admin_config", ["key"])


def _create_verification_notes():
    op.create_table(
        "verification_notes",
        sa.Column("verification_id", sa.String(36), nullable=False),
        sa.Column("admin_id", sa.String(36), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("tags", JSONB_VARIANT, nullable=True),
        sa.Column("pinned", sa.Boolean, nullable=False, default=False),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_verification_notes_id", "verification_notes", ["id"], unique=True)
    op.create_index("ix_verification_notes_deleted", "verification_notes", ["deleted"])
    op.create_index("ix_verification_notes_verification_id", "verification_notes", ["verification_id"])
    op.create_index("ix_verification_notes_admin_id", "verification_notes", ["admin_id"])


def _create_tasks():
    op.create_table(
        "tasks",
        sa.Column("verification_id", sa.String(36), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("agent_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, default="PENDING"),
        sa.Column("pool_released_at", UTCDateTime, nullable=True),
        sa.Column("accepted_at", UTCDateTime, nullable=True),
        sa.Column("submitted_at", UTCDateTime, nullable=True),
        sa.Column("trust_score", sa.Integer, nullable=True),
        sa.Column("draft_payload", sa.Text, nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_tasks_id", "tasks", ["id"], unique=True)
    op.create_index("ix_tasks_deleted", "tasks", ["deleted"])
    op.create_index("ix_tasks_verification_id", "tasks", ["verification_id"])
    op.create_index("ix_tasks_agent_id", "tasks", ["agent_id"])
    op.create_index("ix_tasks_status", "tasks", ["status"])
    op.create_index("ix_tasks_role", "tasks", ["role"])
    # folded analytics index from b8c9d0e1f2a3 (S53)
    op.create_index("ix_tasks_status_accepted_at", "tasks", ["status", "accepted_at"])


def _create_task_assignments():
    op.create_table(
        "task_assignments",
        sa.Column("task_id", sa.String(36), nullable=False),
        sa.Column("agent_id", sa.String(36), nullable=False),
        sa.Column("assigned_by", sa.String(36), nullable=True),
        sa.Column("reassigned_from_id", sa.String(36), nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_task_assignments_id", "task_assignments", ["id"], unique=True)
    op.create_index("ix_task_assignments_deleted", "task_assignments", ["deleted"])
    op.create_index("ix_task_assignments_task_id", "task_assignments", ["task_id"])
    op.create_index("ix_task_assignments_agent_id", "task_assignments", ["agent_id"])


def _create_evidence_items():
    op.create_table(
        "evidence_items",
        sa.Column("task_id", sa.String(36), nullable=False),
        sa.Column("uploader_id", sa.String(36), nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("file_url", sa.Text, nullable=True),
        sa.Column("gps_lat", sa.Float, nullable=True),
        sa.Column("gps_lng", sa.Float, nullable=True),
        sa.Column("captured_at", UTCDateTime, nullable=True),
        sa.Column("details", JSONB_VARIANT, nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_evidence_items_id", "evidence_items", ["id"], unique=True)
    op.create_index("ix_evidence_items_deleted", "evidence_items", ["deleted"])
    op.create_index("ix_evidence_items_task_id", "evidence_items", ["task_id"])
    op.create_index("ix_evidence_items_uploader_id", "evidence_items", ["uploader_id"])


def _create_escalations():
    op.create_table(
        "escalations",
        sa.Column("task_id", sa.String(36), nullable=False),
        sa.Column("reporter_id", sa.String(36), nullable=False),
        sa.Column("category", sa.String(16), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_escalations_id", "escalations", ["id"], unique=True)
    op.create_index("ix_escalations_deleted", "escalations", ["deleted"])
    op.create_index("ix_escalations_task_id", "escalations", ["task_id"])
    op.create_index("ix_escalations_reporter_id", "escalations", ["reporter_id"])


# ─────────────────────────────────────────────────────────────────────
# Conflict flags (orig: f5a6b7c8d9e0)
# ─────────────────────────────────────────────────────────────────────


def _create_conflict_flags():
    op.create_table(
        "conflict_flags",
        sa.Column("verification_id", sa.String(36), nullable=False),
        sa.Column("rule_id", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("resolution_note", sa.Text, nullable=True),
        sa.Column("resolved_by", sa.String(36), nullable=True),
        sa.Column("resolved_at", UTCDateTime, nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_conflict_flags_id", "conflict_flags", ["id"], unique=True)
    op.create_index("ix_conflict_flags_verification_id", "conflict_flags", ["verification_id"])
    op.create_index("ix_conflict_flags_status", "conflict_flags", ["status"])
    op.create_index("ix_conflict_flags_vid_status", "conflict_flags", ["verification_id", "status"])


# ─────────────────────────────────────────────────────────────────────
# Trust score (orig: a1b2c3d4e5f6)
# ─────────────────────────────────────────────────────────────────────


def _create_trust_score_weight_config():
    op.create_table(
        "trust_score_weight_config",
        sa.Column("tier", sa.String(16), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("weight", sa.Numeric(6, 3), nullable=False, default=0),
        *AlembicUtils.base_audit_columns(),
        sa.UniqueConstraint("tier", "role", name="uq_ts_weight_tier_role"),
    )
    op.create_index("ix_ts_weight_config_id", "trust_score_weight_config", ["id"], unique=True)
    op.create_index("ix_ts_weight_config_tier", "trust_score_weight_config", ["tier"])


def _create_trust_score_breakdowns():
    op.create_table(
        "trust_score_breakdowns",
        sa.Column("verification_id", sa.String(36), nullable=False),
        sa.Column("task_scores_json", sa.Text, nullable=False),
        sa.Column("weights_json", sa.Text, nullable=False),
        sa.Column("computed_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("computed_at", UTCDateTime, nullable=False),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_ts_breakdowns_id", "trust_score_breakdowns", ["id"], unique=True)
    op.create_index("ix_ts_breakdowns_verification_id", "trust_score_breakdowns", ["verification_id"])


# ─────────────────────────────────────────────────────────────────────
# Reports (orig: b2c3d4e5f6a7)
# ─────────────────────────────────────────────────────────────────────


def _create_report_views():
    op.create_table(
        "report_views",
        sa.Column("vid", sa.String(24), nullable=False),
        sa.Column("customer_id", sa.String(36), nullable=False),
        sa.Column("acknowledged_at", UTCDateTime, nullable=False),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("report_version", sa.String(16), nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_report_views_id", "report_views", ["id"], unique=True)
    op.create_index("ix_report_views_vid", "report_views", ["vid"])
    op.create_index("ix_report_views_customer_id", "report_views", ["customer_id"])


def _create_report_versions():
    op.create_table(
        "report_versions",
        sa.Column("vid", sa.String(24), nullable=False),
        sa.Column("version_string", sa.String(16), nullable=False),
        sa.Column("pdf_s3_key", sa.String(512), nullable=True),
        sa.Column("is_superseded", sa.Boolean, nullable=False, default=False),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_report_versions_id", "report_versions", ["id"], unique=True)
    op.create_index("ix_report_versions_vid", "report_versions", ["vid"])


# ─────────────────────────────────────────────────────────────────────
# Threads & fraud (orig: c3d4e5f6a7b8)
# ─────────────────────────────────────────────────────────────────────


def _create_message_threads():
    op.create_table(
        "message_threads",
        sa.Column("thread_type", sa.String(20), nullable=False),
        sa.Column("verification_id", sa.String(36), nullable=False),
        sa.Column("task_id", sa.String(36), nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_threads_id", "message_threads", ["id"], unique=True)
    op.create_index("ix_threads_thread_type", "message_threads", ["thread_type"])
    op.create_index("ix_threads_verification_id", "message_threads", ["verification_id"])
    op.create_index("ix_threads_task_id", "message_threads", ["task_id"])
    op.create_index("ix_threads_verification_type", "message_threads", ["verification_id", "thread_type"])


def _create_thread_messages():
    op.create_table(
        "thread_messages",
        sa.Column("thread_id", sa.String(36), nullable=False),
        sa.Column("sender_id", sa.String(36), nullable=True),
        sa.Column("sender_role", sa.String(16), nullable=False),
        sa.Column("message_type", sa.String(16), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("attachment_key", sa.String(512), nullable=True),
        sa.Column("is_held", sa.Boolean, nullable=False, default=False),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_thread_messages_id", "thread_messages", ["id"], unique=True)
    op.create_index("ix_thread_messages_thread_id", "thread_messages", ["thread_id"])


def _create_fraud_flags():
    op.create_table(
        "fraud_flags",
        sa.Column("message_id", sa.String(36), nullable=False),
        sa.Column("message_body", sa.Text, nullable=False),
        sa.Column("matched_patterns", sa.Text, nullable=False),
        sa.Column("reviewed", sa.Boolean, nullable=False, default=False),
        sa.Column("review_decision", sa.String(16), nullable=True),
        sa.Column("reviewer_id", sa.String(36), nullable=True),
        sa.Column("reviewed_at", UTCDateTime, nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_fraud_flags_id", "fraud_flags", ["id"], unique=True)
    op.create_index("ix_fraud_flags_message_id", "fraud_flags", ["message_id"])


# ─────────────────────────────────────────────────────────────────────
# Notifications (orig: d4e5f6a7b8c9)
# ─────────────────────────────────────────────────────────────────────


def _create_notifications():
    op.create_table(
        "notifications",
        sa.Column("recipient_id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("entity_type", sa.String(40), nullable=True),
        sa.Column("entity_id", sa.String(36), nullable=True),
        sa.Column("read", sa.Boolean, nullable=False, default=False),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_notifications_id", "notifications", ["id"], unique=True)
    op.create_index("ix_notifications_recipient_id", "notifications", ["recipient_id"])
    op.create_index("ix_notifications_event_type", "notifications", ["event_type"])


def _create_notification_dispatches():
    op.create_table(
        "notification_dispatches",
        sa.Column("notification_id", sa.String(36), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, default="PENDING"),
        sa.Column("provider_ref", sa.String(200), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_notification_dispatches_id", "notification_dispatches", ["id"], unique=True)
    op.create_index("ix_notification_dispatches_notif_id", "notification_dispatches", ["notification_id"])


def _create_notification_preferences():
    op.create_table(
        "notification_preferences",
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("email_enabled", sa.Boolean, nullable=False, default=True),
        sa.Column("sms_enabled", sa.Boolean, nullable=False, default=False),
        sa.Column("push_enabled", sa.Boolean, nullable=False, default=False),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_notification_preferences_id", "notification_preferences", ["id"], unique=True)
    op.create_index("ix_notification_preferences_user_id", "notification_preferences", ["user_id"])


# ─────────────────────────────────────────────────────────────────────
# Share / recheck / dispute / commission / payout (orig: e5f6a7b8c9d0)
# ─────────────────────────────────────────────────────────────────────


def _create_share_links():
    op.create_table(
        "share_links",
        sa.Column("verification_id", sa.String(36), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False, default="PRIVATE"),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("expires_at", UTCDateTime, nullable=True),
        sa.Column("revoked_at", UTCDateTime, nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_share_links_id", "share_links", ["id"], unique=True)
    op.create_index("ix_share_links_token", "share_links", ["token"], unique=True)
    op.create_index("ix_share_links_verification_id", "share_links", ["verification_id"])


def _create_share_recipients():
    op.create_table(
        "share_recipients",
        sa.Column("share_link_id", sa.String(36), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("acknowledged_at", UTCDateTime, nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_share_recipients_id", "share_recipients", ["id"], unique=True)
    op.create_index("ix_share_recipients_link_id", "share_recipients", ["share_link_id"])


def _create_recheck_requests():
    op.create_table(
        "recheck_requests",
        sa.Column("verification_id", sa.String(36), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("scope_roles", sa.Text, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, default="PENDING"),
        sa.Column("requested_by", sa.String(36), nullable=False),
        sa.Column("reviewed_by", sa.String(36), nullable=True),
        sa.Column("reviewed_at", UTCDateTime, nullable=True),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_recheck_requests_id", "recheck_requests", ["id"], unique=True)
    op.create_index("ix_recheck_requests_verification_id", "recheck_requests", ["verification_id"])


def _create_tier_upgrades():
    op.create_table(
        "tier_upgrades",
        sa.Column("verification_id", sa.String(36), nullable=False),
        sa.Column("from_tier", sa.String(16), nullable=False),
        sa.Column("to_tier", sa.String(16), nullable=False),
        sa.Column("delta_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, default="PENDING"),
        sa.Column("requested_by", sa.String(36), nullable=False),
        sa.Column("payment_id", sa.String(36), nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_tier_upgrades_id", "tier_upgrades", ["id"], unique=True)
    op.create_index("ix_tier_upgrades_verification_id", "tier_upgrades", ["verification_id"])


def _create_disputes():
    op.create_table(
        "disputes",
        sa.Column("verification_id", sa.String(36), nullable=False),
        sa.Column("dispute_type", sa.String(40), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, default="PENDING"),
        sa.Column("submitted_by", sa.String(36), nullable=False),
        sa.Column("submitted_at", UTCDateTime, nullable=False),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_disputes_id", "disputes", ["id"], unique=True)
    op.create_index("ix_disputes_verification_id", "disputes", ["verification_id"])


def _create_dispute_resolutions():
    op.create_table(
        "dispute_resolutions",
        sa.Column("dispute_id", sa.String(36), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("resolution_note", sa.Text, nullable=True),
        sa.Column("resolved_by", sa.String(36), nullable=False),
        sa.Column("resolved_at", UTCDateTime, nullable=False),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_dispute_resolutions_id", "dispute_resolutions", ["id"], unique=True)
    op.create_index("ix_dispute_resolutions_dispute_id", "dispute_resolutions", ["dispute_id"])


def _create_commission_rules():
    op.create_table(
        "commission_rules",
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("tier", sa.String(16), nullable=False),
        sa.Column("percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("effective_date", sa.Date, nullable=False),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_commission_rules_id", "commission_rules", ["id"], unique=True)
    op.create_index("ix_commission_rules_role_tier", "commission_rules", ["role", "tier"])


def _create_earnings():
    op.create_table(
        "earnings",
        sa.Column("agent_id", sa.String(36), nullable=False),
        sa.Column("task_id", sa.String(36), nullable=False),
        sa.Column("verification_id", sa.String(36), nullable=False),
        sa.Column("gross_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("commission_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("net_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, default="PENDING"),
        sa.Column("computed_at", UTCDateTime, nullable=False),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_earnings_id", "earnings", ["id"], unique=True)
    op.create_index("ix_earnings_agent_id", "earnings", ["agent_id"])
    op.create_index("ix_earnings_task_id", "earnings", ["task_id"])


def _create_bank_accounts():
    op.create_table(
        "bank_accounts",
        sa.Column("agent_id", sa.String(36), nullable=False),
        sa.Column("bank_name", sa.String(100), nullable=False),
        sa.Column("account_number", sa.String(20), nullable=False),
        sa.Column("account_holder_name", sa.String(200), nullable=False),
        sa.Column("is_default", sa.Boolean, nullable=False, default=False),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_bank_accounts_id", "bank_accounts", ["id"], unique=True)
    op.create_index("ix_bank_accounts_agent_id", "bank_accounts", ["agent_id"])


def _create_payouts():
    op.create_table(
        "payouts",
        sa.Column("agent_id", sa.String(36), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("bank_account_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, default="PENDING"),
        sa.Column("requested_at", UTCDateTime, nullable=False),
        sa.Column("approved_at", UTCDateTime, nullable=True),
        sa.Column("paid_at", UTCDateTime, nullable=True),
        sa.Column("hold_reason", sa.Text, nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_payouts_id", "payouts", ["id"], unique=True)
    op.create_index("ix_payouts_agent_id", "payouts", ["agent_id"])


def _create_payout_adjustments():
    op.create_table(
        "payout_adjustments",
        sa.Column("payout_id", sa.String(36), nullable=False),
        sa.Column("adjusted_by", sa.String(36), nullable=False),
        sa.Column("original_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("new_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_payout_adjustments_id", "payout_adjustments", ["id"], unique=True)
    op.create_index("ix_payout_adjustments_payout_id", "payout_adjustments", ["payout_id"])


# ─────────────────────────────────────────────────────────────────────
# Agent quality scores (orig: f6a7b8c9d0e1)
# ─────────────────────────────────────────────────────────────────────


def _create_agent_quality_scores():
    op.create_table(
        "agent_quality_scores",
        sa.Column("task_id", sa.String(36), nullable=False),
        sa.Column("agent_id", sa.String(36), nullable=False),
        sa.Column("score", sa.SmallInteger, nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("reviewed_by_admin_id", sa.String(36), nullable=False),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_agent_quality_scores_id", "agent_quality_scores", ["id"], unique=True)
    op.create_index("ix_agent_quality_scores_task_id", "agent_quality_scores", ["task_id"], unique=True)
    op.create_index("ix_agent_quality_scores_agent_id", "agent_quality_scores", ["agent_id"])


# ─────────────────────────────────────────────────────────────────────
# Referrals (orig: a7b8c9d0e1f2)
# ─────────────────────────────────────────────────────────────────────


def _create_referral_codes():
    op.create_table(
        "referral_codes",
        sa.Column("owner_id", sa.String(36), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("times_redeemed", sa.Integer, nullable=False, server_default="0"),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_referral_codes_id", "referral_codes", ["id"], unique=True)
    op.create_index("ix_referral_codes_owner_id", "referral_codes", ["owner_id"], unique=True)
    op.create_index("ix_referral_codes_code", "referral_codes", ["code"], unique=True)


def _create_referral_redemptions():
    op.create_table(
        "referral_redemptions",
        sa.Column("referral_code_id", sa.String(36), nullable=False),
        sa.Column("invitee_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("credited_at", UTCDateTime, nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_referral_redemptions_id", "referral_redemptions", ["id"], unique=True)
    op.create_index("ix_referral_redemptions_invitee_id", "referral_redemptions", ["invitee_id"], unique=True)
    op.create_index("ix_referral_redemptions_code_id", "referral_redemptions", ["referral_code_id"])


# ─────────────────────────────────────────────────────────────────────
# Pricing (orig: c9d0e1f2a3b4)
# ─────────────────────────────────────────────────────────────────────


def _create_pricing_tier_configs():
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


def _create_pricing_line_items():
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


def _create_pricing_upgrade_deltas():
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


# ─────────────────────────────────────────────────────────────────────
# Content & broadcast (orig: d0e1f2a3b4c5)
# ─────────────────────────────────────────────────────────────────────


def _create_content_items():
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


def _create_broadcasts():
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


# ─────────────────────────────────────────────────────────────────────
# Data erasure (orig: e1f2a3b4c5d6)
# ─────────────────────────────────────────────────────────────────────


def _create_data_erasure_requests():
    op.create_table(
        "data_erasure_requests",
        sa.Column("user_id", sa.String(36), nullable=False, index=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("requested_at", UTCDateTime, nullable=False),
        sa.Column("reviewed_by", sa.String(36), nullable=True),
        sa.Column("reviewed_at", UTCDateTime, nullable=True),
        sa.Column("executed_at", UTCDateTime, nullable=True),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index(
        "ix_data_erasure_requests_user_status",
        "data_erasure_requests",
        ["user_id", "status"],
    )


# ─────────────────────────────────────────────────────────────────────
# Seed data
# ─────────────────────────────────────────────────────────────────────

CONSENT_SEEDS = [
    ("PLATFORM_TERMS", "1.0.0", "Platform Terms of Service", "/legal/terms"),
    ("PRIVACY_POLICY", "1.0.0", "Privacy Policy", "/legal/privacy"),
    ("AGENT_TERMS", "1.0.0", "Agent Terms", "/legal/agent-terms"),
    ("VERIFICATION_TERMS", "1.0.0", "Verification Terms", "/legal/verification-terms"),
    ("REPORT_DISCLAIMER", "1.0.0", "Report Disclaimer", "/legal/report-disclaimer"),
]

VERIFICATION_CONSENT_SEEDS = [
    ("VERIFICATION_DISCLAIMER", "1.0.0", "Verification Disclaimer", "/legal/verification-disclaimer"),
    ("FINDINGS_OPINION_ACK", "1.0.0", "Findings & Opinion Acknowledgement", "/legal/findings-opinion"),
    ("JURISDICTION_PLATFORM_ONLY", "1.0.0", "Jurisdiction & Platform-Only Transactions", "/legal/jurisdiction"),
    ("COMMUNICATION_RECORDING", "1.0.0", "Communication Recording", "/legal/communication-recording"),
    ("REFUND_POLICY", "1.0.0", "Refund & Cancellation Policy", "/legal/refund-policy"),
]

# Provisional trust-score weights (D2 decision)
_SEED_WEIGHTS = [
    ("BASIC", "REGISTRY", "100.000"),
    ("STANDARD", "FIELD", "35.000"),
    ("STANDARD", "SURVEYOR", "30.000"),
    ("STANDARD", "REGISTRY", "35.000"),
    ("PREMIUM", "FIELD", "25.000"),
    ("PREMIUM", "SURVEYOR", "20.000"),
    ("PREMIUM", "REGISTRY", "30.000"),
    ("PREMIUM", "LAWYER", "25.000"),
]


def _seed_audit_columns(now: datetime) -> dict:
    return {
        "date_created": now,
        "date_updated": None,
        "deleted": False,
        "version": 1,
    }


def _seed_consent_documents() -> None:
    consent_documents = sa.table(
        "consent_documents",
        sa.column("id", sa.UUID),
        sa.column("type", sa.String),
        sa.column("consent_version", sa.String),
        sa.column("effective_at", UTCDateTime),
        sa.column("title", sa.String),
        sa.column("href", sa.String),
        sa.column("date_created", UTCDateTime),
        sa.column("deleted", sa.Boolean),
        sa.column("version", sa.Integer),
    )

    now = Utils.datetime_now()

    op.bulk_insert(
        consent_documents,
        [
            {
                "id": Utils.generate_uuid(),
                "type": doc_type,
                "consent_version": consent_version,
                "effective_at": now,
                "title": title,
                "href": href,
                **_seed_audit_columns(now),
            }
            for doc_type, consent_version, title, href in CONSENT_SEEDS
        ],
    )


def _seed_verification_consents() -> None:
    """Idempotent insert of the verification-stage consent documents."""
    conn = op.get_bind()
    eff = datetime(2026, 5, 1, tzinfo=timezone.utc)
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
                "id": Utils.generate_uuid(),
                "type": doc_type,
                "ver": ver,
                "eff": eff,
                "title": title,
                "href": href,
                "now": Utils.datetime_now(),
            },
        )


def _seed_super_admin() -> None:
    """Seed the first Super Admin from env. Idempotent on canonical email."""
    password = settings.SUPER_ADMIN_PASSWORD
    email = settings.SUPER_ADMIN_EMAIL
    if not password or not email:
        raise ValueError("Super Admin details not set.")

    conn = op.get_bind()
    existing = conn.execute(
        sa.text("SELECT 1 FROM users WHERE email = :email LIMIT 1"),
        {"email": email},
    ).first()
    if existing:
        return

    password_hash = Utils.get_password_hash(password)
    now = datetime.now(timezone.utc)
    conn.execute(
        sa.text(
            """
            INSERT INTO users (
                id, first_name, last_name, email, email_normalized, email_verified,
                phone_country_code, phone_dial_code, phone, phone_e164, phone_verified,
                country_of_residence, timezone, preferred_currency,
                user_type, personas, admin_sub_role, trust_status,
                password_hash, failed_login_count,
                date_created, deleted, version
            )
            VALUES (
                :id, :first_name, :last_name, :email, :email_normalized, TRUE,
                :ccode, :dial, :phone, :phone_e164, TRUE,
                :country, :tz, :currency,
                :user_type, :personas, :sub_role, :trust,
                :password_hash, 0,
                :now, FALSE, 1
            )
            """
        ),
        {
            "id": str(Utils.generate_uuid()),
            "first_name": "Veriprops",
            "last_name": "Admin",
            "email": email,
            "email_normalized": email.strip().lower(),
            "ccode": "NG",
            "dial": "+234",
            "phone": "7039018727",
            "phone_e164": "+2347039018727",
            "country": "NG",
            "tz": "Africa/Lagos",
            "currency": "NGN",
            "user_type": "ADMIN",
            "personas": json.dumps([]),
            "sub_role": "SUPER",
            "trust": "TRUSTED",
            "password_hash": password_hash,
            "now": now,
        },
    )


def _seed_trust_score_weights() -> None:
    now = datetime.now(timezone.utc)
    weight_table = sa.table(
        "trust_score_weight_config",
        sa.column("id", sa.UUID),
        sa.column("date_created", UTCDateTime),
        sa.column("version", sa.Integer),
        sa.column("deleted", sa.Boolean),
        sa.column("tier", sa.String),
        sa.column("role", sa.String),
        sa.column("weight", sa.Numeric),
    )
    op.bulk_insert(weight_table, [
        {"id": str(Utils.generate_uuid()), "date_created": now, "version": 1, "deleted": False,
         "tier": tier, "role": role, "weight": weight}
        for tier, role, weight in _SEED_WEIGHTS
    ])


def _seed_pricing() -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)

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
            "id": str(Utils.generate_uuid()), "tier": "BASIC", "label": "Basic verification (registry-only)",
            "currency": "NGN", "service_fee_minor": 1500000, "is_active": True,
            "updated_by": None, "date_created": now, "date_updated": None, "deleted": False, "version": 1,
            "line_items": [
                {"label": "Registry search", "amount_minor": 13000000,
                 "description": "Title search at the registry of record", "sort_order": 0},
                {"label": "Document collection", "amount_minor": 500000,
                 "description": "Acquisition of certified true copies", "sort_order": 1},
            ],
        },
        {
            "id": str(Utils.generate_uuid()), "tier": "STANDARD",
            "label": "Standard verification (registry + field + survey)",
            "currency": "NGN", "service_fee_minor": 2500000, "is_active": True,
            "updated_by": None, "date_created": now, "date_updated": None, "deleted": False, "version": 1,
            "line_items": [
                {"label": "Registry search", "amount_minor": 13000000,
                 "description": "Title search at the registry of record", "sort_order": 0},
                {"label": "Document collection", "amount_minor": 500000,
                 "description": "Acquisition of certified true copies", "sort_order": 1},
                {"label": "Field inspection", "amount_minor": 9000000,
                 "description": "On-site inspection by Field Agent", "sort_order": 2},
                {"label": "Survey assessment", "amount_minor": 10000000,
                 "description": "Boundary + survey-plan check", "sort_order": 3},
            ],
        },
        {
            "id": str(Utils.generate_uuid()), "tier": "PREMIUM",
            "label": "Premium verification (full + legal opinion)",
            "currency": "NGN", "service_fee_minor": 5000000, "is_active": True,
            "updated_by": None, "date_created": now, "date_updated": None, "deleted": False, "version": 1,
            "line_items": [
                {"label": "Registry search", "amount_minor": 13000000,
                 "description": "Title search at the registry of record", "sort_order": 0},
                {"label": "Document collection", "amount_minor": 500000,
                 "description": "Acquisition of certified true copies", "sort_order": 1},
                {"label": "Field inspection", "amount_minor": 9000000,
                 "description": "On-site inspection by Field Agent", "sort_order": 2},
                {"label": "Survey assessment", "amount_minor": 12000000,
                 "description": "Boundary + survey-plan check", "sort_order": 3},
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
                    "id": str(Utils.generate_uuid()),
                    "tier_config_id": config_id,
                    "label": li["label"],
                    "amount_minor": li["amount_minor"],
                    "description": li["description"],
                    "sort_order": li["sort_order"],
                    "date_created": now,
                    "date_updated": None,
                    "deleted": False,
                    "version": 1,
                }
                for li in line_items_data
            ],
        )


def _seed_content_items() -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    content_items = sa.table(
        "content_items",
        sa.column("id"), sa.column("item_type"), sa.column("slug"), sa.column("title"),
        sa.column("body"), sa.column("details"), sa.column("is_published"), sa.column("sort_order"),
        sa.column("author_id"), sa.column("lga"), sa.column("state"),
        sa.column("date_created"), sa.column("date_updated"), sa.column("deleted"), sa.column("version"),
    )

    how_it_works = [
        {
            "id": str(Utils.generate_uuid()), "item_type": "HOW_IT_WORKS_STEP", "sort_order": 0,
            "slug": "hiw-step-1-submit-details", "title": "Submit Details",
            "body": "Provide property coordinates, upload documents, and select your verification tier.",
            "details": None, "is_published": True, "author_id": None, "lga": None, "state": None,
            "date_created": now, "date_updated": None, "deleted": False, "version": 1,
        },
        {
            "id": str(Utils.generate_uuid()), "item_type": "HOW_IT_WORKS_STEP", "sort_order": 1,
            "slug": "hiw-step-2-cross-check-records", "title": "Cross-Check Records",
            "body": "We validate ownership against official registry and survey records with certified agents.",
            "details": None, "is_published": True, "author_id": None, "lga": None, "state": None,
            "date_created": now, "date_updated": None, "deleted": False, "version": 1,
        },
        {
            "id": str(Utils.generate_uuid()), "item_type": "HOW_IT_WORKS_STEP", "sort_order": 2,
            "slug": "hiw-step-3-check-encumbrances", "title": "Check Encumbrances",
            "body": "Identify liens, caveats, pending litigations, or any outstanding claims on the property.",
            "details": None, "is_published": True, "author_id": None, "lga": None, "state": None,
            "date_created": now, "date_updated": None, "deleted": False, "version": 1,
        },
        {
            "id": str(Utils.generate_uuid()), "item_type": "HOW_IT_WORKS_STEP", "sort_order": 3,
            "slug": "hiw-step-4-run-risk-analysis", "title": "Run Risk Analysis",
            "body": "Assessment of area zoning, title history, fraud indicators, and surrounding property context.",
            "details": None, "is_published": True, "author_id": None, "lga": None, "state": None,
            "date_created": now, "date_updated": None, "deleted": False, "version": 1,
        },
        {
            "id": str(Utils.generate_uuid()), "item_type": "HOW_IT_WORKS_STEP", "sort_order": 4,
            "slug": "hiw-step-5-get-certified-report", "title": "Get Certified Report",
            "body": "Receive your high-authority digital report with Trust Score, Verification ID, and agent sign-offs.",
            "details": None, "is_published": True, "author_id": None, "lga": None, "state": None,
            "date_created": now, "date_updated": None, "deleted": False, "version": 1,
        },
    ]

    testimonials = [
        {
            "id": str(Utils.generate_uuid()), "item_type": "TESTIMONIAL", "sort_order": 0,
            "slug": "testimonial-emeka-okafor",
            "title": "Emeka Okafor — London, UK",
            "body": "I was about to wire £65,000 for a property in Lekki. Veriprops found three competing ownership claims before I paid a penny. This service saved my family's financial future.",
            "details": '{"tier":"Premium","initials":"EO"}',
            "is_published": True, "author_id": None, "lga": None, "state": None,
            "date_created": now, "date_updated": None, "deleted": False, "version": 1,
        },
        {
            "id": str(Utils.generate_uuid()), "item_type": "TESTIMONIAL", "sort_order": 1,
            "slug": "testimonial-adaeze-williams",
            "title": "Adaeze Williams — Houston, TX",
            "body": "The Standard report was thorough — GPS-stamped photos, boundary survey, full registry search — all delivered within 6 days. Exactly what I needed from 7,000 miles away.",
            "details": '{"tier":"Standard","initials":"AW"}',
            "is_published": True, "author_id": None, "lga": None, "state": None,
            "date_created": now, "date_updated": None, "deleted": False, "version": 1,
        },
        {
            "id": str(Utils.generate_uuid()), "item_type": "TESTIMONIAL", "sort_order": 2,
            "slug": "testimonial-chukwudi-nwosu",
            "title": "Chukwudi Nwosu — Toronto, Canada",
            "body": "The Trust Score concept is genius. I now only consider properties scoring above 80. It has fundamentally changed how I approach Nigerian real estate investment.",
            "details": '{"tier":"Basic","initials":"CN"}',
            "is_published": True, "author_id": None, "lga": None, "state": None,
            "date_created": now, "date_updated": None, "deleted": False, "version": 1,
        },
    ]

    op.bulk_insert(content_items, how_it_works + testimonials)


# ─────────────────────────────────────────────────────────────────────
# Table registry (build order). Drops run in reverse.
# ─────────────────────────────────────────────────────────────────────

_TABLE_BUILDERS = [
    ("users", _create_users),
    ("key_values", _create_key_values),
    ("oauth_identities", _create_oauth_identities),
    ("consent_documents", _create_consent_documents),
    ("user_consents", _create_user_consents),
    ("device_sessions", _create_device_sessions),
    ("security_events", _create_security_events),
    ("password_reset_tokens", _create_password_reset_tokens),
    ("signup_drafts", _create_signup_drafts),
    ("messages", _create_messages),
    ("agent_applications", _create_agent_applications),
    ("admin_invitations", _create_admin_invitations),
    ("properties", _create_properties),
    ("verifications", _create_verifications),
    ("payments", _create_payments),
    ("payment_attempts", _create_payment_attempts),
    ("audit_logs", _create_audit_logs),
    ("kyc_records", _create_kyc_records),
    ("admin_config", _create_admin_config),
    ("verification_notes", _create_verification_notes),
    ("tasks", _create_tasks),
    ("task_assignments", _create_task_assignments),
    ("evidence_items", _create_evidence_items),
    ("escalations", _create_escalations),
    ("conflict_flags", _create_conflict_flags),
    ("trust_score_weight_config", _create_trust_score_weight_config),
    ("trust_score_breakdowns", _create_trust_score_breakdowns),
    ("report_views", _create_report_views),
    ("report_versions", _create_report_versions),
    ("message_threads", _create_message_threads),
    ("thread_messages", _create_thread_messages),
    ("fraud_flags", _create_fraud_flags),
    ("notifications", _create_notifications),
    ("notification_dispatches", _create_notification_dispatches),
    ("notification_preferences", _create_notification_preferences),
    ("share_links", _create_share_links),
    ("share_recipients", _create_share_recipients),
    ("recheck_requests", _create_recheck_requests),
    ("tier_upgrades", _create_tier_upgrades),
    ("disputes", _create_disputes),
    ("dispute_resolutions", _create_dispute_resolutions),
    ("commission_rules", _create_commission_rules),
    ("earnings", _create_earnings),
    ("bank_accounts", _create_bank_accounts),
    ("payouts", _create_payouts),
    ("payout_adjustments", _create_payout_adjustments),
    ("agent_quality_scores", _create_agent_quality_scores),
    ("referral_codes", _create_referral_codes),
    ("referral_redemptions", _create_referral_redemptions),
    ("pricing_tier_configs", _create_pricing_tier_configs),
    ("pricing_line_items", _create_pricing_line_items),
    ("pricing_upgrade_deltas", _create_pricing_upgrade_deltas),
    ("content_items", _create_content_items),
    ("broadcasts", _create_broadcasts),
    ("data_erasure_requests", _create_data_erasure_requests),
]


def upgrade() -> None:
    for name, builder in _TABLE_BUILDERS:
        if not AlembicUtils.table_exists(name):
            builder()

    # Data seeds belong here, not in app-level seeders.
    if AlembicUtils.table_exists("consent_documents"):
        _seed_consent_documents()
        _seed_verification_consents()
    if AlembicUtils.table_exists("users"):
        _seed_super_admin()
    if AlembicUtils.table_exists("trust_score_weight_config"):
        _seed_trust_score_weights()
    if AlembicUtils.table_exists("pricing_tier_configs") and AlembicUtils.table_exists("pricing_line_items"):
        _seed_pricing()
    if AlembicUtils.table_exists("content_items"):
        _seed_content_items()


def downgrade() -> None:
    for name, _builder in reversed(_TABLE_BUILDERS):
        if AlembicUtils.table_exists(name):
            op.drop_table(name)
