"""initial_schema — full Veriprops schema in one migration.

This single migration is a squash of the original 20-file chain
(fdd959a2cfda … f3a4b5c6d7e8), later re-squashed to fold in
0002_user_account_status (users.account_status/suspended_*) and
0003_user_verify_started (users.has_started_verification), and re-squashed
again to fold in the ten-file WhatsApp cycle (0002_whatsapp_channel …
0011_whatsapp_legal_copy) once every environment had been migrated past it.
Every table is created once in its final shape: later add_column /
alter_column steps are folded into the relevant CREATE TABLE, and JSON
columns are declared with ``JSONB_VARIANT`` so the former Postgres-only
JSON→JSONB pass is unnecessary.

A squash is only safe once every live database is stamped at the head being
folded in, because ``revision`` below becomes that head: an already-migrated
database matches it and does nothing, and a fresh one builds the same schema
in one step. That is the invariant to re-establish before squashing again —
not the file's name, which has never been its revision id.

Each table lives in its own ``_create_<table>()`` helper (mirroring the
original auto_generated migration) and reuses ``AlembicUtils`` helpers.

All reference seed data lands here too — there is no app-startup seeder.
Every writer is idempotent (safe to re-run on an already-seeded database),
and the rows are sourced from the app-side registries so nothing is
duplicated: legal-document content (``LEGAL_DOCUMENT_CONTENT``), the super
admin (``settings``), trust-score weights (``DEFAULT_TRUST_WEIGHTS``),
system config (``CONFIG_DEFAULTS``), commission rules (derived from the
weights, D30), and pricing tiers + line items (``TIER_PRICE_NGN_KOBO``).
Enum members are reduced to their raw ``.value`` strings at row-build time,
keeping the emitted SQL decoupled from app enums.

Revision ID: 0011_whatsapp_legal_copy
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
from main.app.domain.commission_rule.models import BPS_PER_PERCENT
from main.app.domain.system_config.models import CONFIG_DEFAULTS, CONFIG_DESCRIPTIONS
from main.app.domain.user.auth.consent.content import LEGAL_DOCUMENT_CONTENT
from main.app.domain.verification.pricing import TIER_PRICE_NGN_KOBO
from main.app.domain.verification.scoring.models import DEFAULT_TRUST_WEIGHTS
from main.appodus_utils import Utils
from main.appodus_utils.db.models import UTCDateTime, JSONB_VARIANT

# revision identifiers, used by Alembic. The id is the *last* revision folded in, not the
# filename: a database already stamped at that revision is left alone by this squash, which
# is what makes re-squashing safe on live environments (the previous squash kept
# `0003_user_verify_started` for the same reason).
revision: str = "0011_whatsapp_legal_copy"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Raw strings by design — migrations stay decoupled from app enums.
_CHANNEL_WEB = "WEB"
_SOURCE_WEB = "WEB"
_MODE_BOT = "BOT"
_STATUS_PENDING = "PENDING"
_STATUS_NOT_FOUND = "NOT_FOUND"
_QUALITY_UNKNOWN = "UNKNOWN"


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
        # §17.1 referral linkage — the referrer this user signed up under (S21).
        sa.Column("referred_by", sa.String(length=36), nullable=True),
        # folded from 0002_user_account_status (PRD §2.4a) — admin-controlled suspension.
        sa.Column("account_status", sa.String(length=16), nullable=False, server_default="ACTIVE"),
        sa.Column("suspended_at", UTCDateTime, nullable=True),
        sa.Column("suspension_reason", sa.String(length=500), nullable=True),
        # Admin user id (36-char str form) — application-enforced reference, no FK.
        sa.Column("suspended_by", sa.String(length=36), nullable=True),
        # folded from 0003_user_verify_started — first-login new-verification auto-launch gate.
        sa.Column("has_started_verification", sa.Boolean(), nullable=False, server_default="false"),
        *AlembicUtils.base_audit_columns(),
        sa.UniqueConstraint("email_normalized", name="uq_users_email"),
    )
    op.create_index("ix_users_phone_e164", "users", ["phone_e164"], unique=False)
    op.create_index("ix_users_referred_by", "users", ["referred_by"], unique=False)
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
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("signoff_status", sa.String(length=16), nullable=False, server_default="DRAFT"),
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


def _create_devices():
    op.create_table(
        "devices",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("device_id", sa.String(length=36), nullable=False),
        sa.Column("push_provider_type", sa.String(length=20), nullable=False),
        sa.Column("push_token", JSONB_VARIANT, nullable=False),
        sa.Column("last_active", UTCDateTime, nullable=False),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_devices_user_id", "devices", ["user_id"], unique=False)
    op.create_index("ix_devices_id", "devices", ["id"], unique=True)


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
        sa.Column("next_retry_at", UTCDateTime, nullable=True),
        sa.Column("expires_at", UTCDateTime, nullable=True),
        sa.Column("sent_at", UTCDateTime, nullable=True),
        sa.Column("delivered_at", UTCDateTime, nullable=True),
        sa.Column("extras", JSONB_VARIANT, nullable=True),
        sa.Column("callback_url", sa.String(length=100), nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index(op.f("ix_messages_deleted"), "messages", ["deleted"], unique=False)
    op.create_index(op.f("ix_messages_id"), "messages", ["id"], unique=True)
    # Retry-sweep hot path — name must match the model's __table_args__ Index exactly.
    op.create_index("ix_messages_status_next_retry_at", "messages", ["status", "next_retry_at"], unique=False)


def _create_callbacks():
    op.create_table(
        "callbacks",
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("event_type", sa.String(length=20), nullable=False),
        sa.Column("external_id", sa.String(length=97), nullable=False),
        sa.Column("payload", JSONB_VARIANT, nullable=False),
        sa.Column("handle_from_time", UTCDateTime, nullable=False),
        sa.Column("handled", sa.Boolean(), nullable=False, server_default="false"),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_callbacks_external_id", "callbacks", ["external_id"], unique=False)
    op.create_index("ix_callbacks_handled", "callbacks", ["handled"], unique=False)
    op.create_index("ix_callbacks_id", "callbacks", ["id"], unique=True)

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
# Idempotency keys (PRD §4.6) — payments + entity creation
# ─────────────────────────────────────────────────────────────────────


def _create_idempotency_keys():
    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("scope", sa.String(length=64), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("response_snapshot", JSONB_VARIANT, nullable=True),
        sa.Column("resource_id", sa.String(length=36), nullable=True),
        sa.Column("expires_at", UTCDateTime, nullable=False),
        *AlembicUtils.base_audit_columns(),
        sa.UniqueConstraint("key", name="uq_idempotency_key"),
    )
    op.create_index("ix_idempotency_keys_id", "idempotency_keys", ["id"], unique=True)
    op.create_index("ix_idempotency_keys_deleted", "idempotency_keys", ["deleted"], unique=False)
    op.create_index("ix_idempotency_scope_expires", "idempotency_keys", ["scope", "expires_at"], unique=False)


# ─────────────────────────────────────────────────────────────────────
# Agent onboarding & KYC (PRD §3.1–3.2, §3.3a)
# ─────────────────────────────────────────────────────────────────────


def _create_agent_profiles():
    op.create_table(
        "agent_profiles",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("roles", JSONB_VARIANT, nullable=False),
        sa.Column("approved_roles", JSONB_VARIANT, nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="PENDING"),
        sa.Column("rejection_reason", sa.String(length=500), nullable=True),
        sa.Column("bio", sa.String(length=300), nullable=True),
        sa.Column("years_experience", sa.Integer(), nullable=True),
        sa.Column("availability", sa.String(length=8), nullable=False, server_default="GREEN"),
        sa.Column("submitted_at", UTCDateTime, nullable=True),
        sa.Column("reviewed_at", UTCDateTime, nullable=True),
        sa.Column("reviewed_by", sa.String(length=36), nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_agent_profiles_id", "agent_profiles", ["id"], unique=True)
    op.create_index("ix_agent_profiles_user_id", "agent_profiles", ["user_id"], unique=False)
    op.create_index("ix_agent_profiles_status", "agent_profiles", ["status"], unique=False)


def _create_agent_credentials():
    op.create_table(
        "agent_credentials",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("credential_type", sa.String(length=32), nullable=False),
        sa.Column("licence_number", sa.String(length=64), nullable=True),
        sa.Column("document_ref", sa.String(length=512), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="PENDING"),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_agent_credentials_id", "agent_credentials", ["id"], unique=True)
    op.create_index("ix_agent_credentials_user_id", "agent_credentials", ["user_id"], unique=False)


def _create_agent_coverage():
    op.create_table(
        "agent_coverage",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("state", sa.String(length=64), nullable=False),
        sa.Column("lga", sa.String(length=64), nullable=True),
        sa.Column("place", sa.String(length=255), nullable=True),
        sa.Column("travel_radius_km", sa.Integer(), nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_agent_coverage_id", "agent_coverage", ["id"], unique=True)
    op.create_index("ix_agent_coverage_user_id", "agent_coverage", ["user_id"], unique=False)


def _create_agent_application_drafts():
    op.create_table(
        "agent_application_drafts",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("expires_at", UTCDateTime, nullable=False),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_agent_application_drafts_id", "agent_application_drafts", ["id"], unique=True)
    op.create_index("ix_agent_application_drafts_user_id", "agent_application_drafts", ["user_id"], unique=False)


def _create_admin_invitations():
    op.create_table(
        "admin_invitations",
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("email_normalized", sa.String(length=254), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=True),
        sa.Column("last_name", sa.String(length=100), nullable=True),
        sa.Column("sub_role", sa.String(length=16), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="PENDING"),
        sa.Column("invited_by", sa.String(length=36), nullable=False),
        sa.Column("expires_at", UTCDateTime, nullable=False),
        sa.Column("accepted_at", UTCDateTime, nullable=True),
        sa.Column("accepted_by", sa.String(length=36), nullable=True),
        *AlembicUtils.base_audit_columns(),
        sa.UniqueConstraint("token_hash", name="uq_admin_invitation_token_hash"),
    )
    op.create_index("ix_admin_invitations_id", "admin_invitations", ["id"], unique=True)
    op.create_index("ix_admin_invitations_email", "admin_invitations", ["email"], unique=False)
    op.create_index("ix_admin_invitations_email_norm", "admin_invitations", ["email_normalized"], unique=False)
    op.create_index("ix_admin_invitations_token_hash", "admin_invitations", ["token_hash"], unique=False)


def _create_kyc_records():
    op.create_table(
        "kyc_records",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("provider_ref", sa.String(length=255), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("summary", sa.String(length=500), nullable=True),
        sa.Column("verified_at", UTCDateTime, nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_kyc_records_id", "kyc_records", ["id"], unique=True)
    op.create_index("ix_kyc_records_user_id", "kyc_records", ["user_id"], unique=False)


# ─────────────────────────────────────────────────────────────────────
# Property / Verification / Payment (PRD §4.3, §4.4, §5)
# ─────────────────────────────────────────────────────────────────────


def _create_properties():
    op.create_table(
        "properties",
        sa.Column("customer_id", sa.String(length=36), nullable=False),
        sa.Column("property_type", sa.String(length=16), nullable=False),
        sa.Column("address", sa.String(length=512), nullable=True),
        sa.Column("landmark", sa.String(length=512), nullable=True),
        sa.Column("state", sa.String(length=64), nullable=True),
        sa.Column("lga", sa.String(length=64), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("place_id", sa.String(length=255), nullable=True),
        sa.Column("details", JSONB_VARIANT, nullable=True),
        sa.Column("seller", JSONB_VARIANT, nullable=True),
        sa.Column("documents", JSONB_VARIANT, nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_properties_id", "properties", ["id"], unique=True)
    op.create_index("ix_properties_customer_id", "properties", ["customer_id"], unique=False)


def _create_verifications():
    op.create_table(
        "verifications",
        sa.Column("vid", sa.String(length=16), nullable=False),
        sa.Column("customer_id", sa.String(length=36), nullable=False),
        sa.Column("property_id", sa.String(length=36), nullable=True),
        sa.Column("tier", sa.String(length=16), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="DRAFT"),
        sa.Column("price_locked_minor", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="NGN"),
        sa.Column("charge_currency", sa.String(length=8), nullable=True),
        sa.Column("charge_amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("fx_rate_at_quote", sa.Float(), nullable=True),
        sa.Column("price_lock_expires_at", UTCDateTime, nullable=True),
        # Growth discounts recorded at submit (§17.1, S21); price_locked_minor is the NET.
        sa.Column("first_time_discount_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("referral_credit_applied_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("consent_snapshot_id", sa.String(length=36), nullable=True),
        sa.Column("draft_step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("draft_payload", sa.Text(), nullable=True),
        sa.Column("paid_at", UTCDateTime, nullable=True),
        sa.Column("sla_due_date", sa.Date(), nullable=True),
        # Abandoned-draft recovery marker (§17.1, S21) — one reminder ever.
        sa.Column("recovery_reminded_at", UTCDateTime, nullable=True),
        # Admin operational hold (§26.5) — a flag, not a state (see Verification model).
        sa.Column("paused", sa.Boolean(), nullable=False, server_default="false"),
        # Public VID-lookup visibility (§13.1 "Public" sharing mode).
        sa.Column("public_lookup_enabled", sa.Boolean(), nullable=False, server_default="false"),
        # Pending report re-version reason for the next release (§14): RECHECK / TIER_UPGRADE.
        sa.Column("pending_revision_kind", sa.String(length=16), nullable=True),
        *AlembicUtils.base_audit_columns(),
        sa.UniqueConstraint("vid", name="uq_verifications_vid"),
    )
    op.create_index("ix_verifications_id", "verifications", ["id"], unique=True)
    op.create_index("ix_verifications_vid", "verifications", ["vid"], unique=False)
    op.create_index("ix_verifications_customer_id", "verifications", ["customer_id"], unique=False)
    op.create_index("ix_verifications_property_id", "verifications", ["property_id"], unique=False)
    op.create_index("ix_verifications_status", "verifications", ["status"], unique=False)


def _create_payments():
    op.create_table(
        "payments",
        sa.Column("verification_id", sa.String(length=36), nullable=False),
        sa.Column("customer_id", sa.String(length=36), nullable=False),
        # What the charge is for (§14): INITIAL / RECHECK / UPGRADE.
        sa.Column("purpose", sa.String(length=16), nullable=False, server_default="INITIAL"),
        sa.Column("tx_ref", sa.String(length=64), nullable=False),
        sa.Column("gateway_event_id", sa.String(length=128), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=True),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="INITIATED"),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="NGN"),
        sa.Column("charge_currency", sa.String(length=8), nullable=True),
        sa.Column("charge_amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("checkout_url", sa.String(length=1024), nullable=True),
        # Anti-farming instrument marker (§17.1 / D34, S21) — gateway card fingerprint, never
        # raw card data. Null under PAYMENT_STUB_MODE.
        sa.Column("card_fingerprint", sa.String(length=128), nullable=True),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        # Chargeback flag (§6a.1) — sub-process detail lives on the chargebacks row.
        sa.Column("chargeback_status", sa.String(length=24), nullable=True),
        sa.Column("refunded_amount_minor", sa.BigInteger(), nullable=True),
        *AlembicUtils.base_audit_columns(),
        sa.UniqueConstraint("tx_ref", name="uq_payments_tx_ref"),
    )
    op.create_index("ix_payments_id", "payments", ["id"], unique=True)
    op.create_index("ix_payments_verification_id", "payments", ["verification_id"], unique=False)
    op.create_index("ix_payments_customer_id", "payments", ["customer_id"], unique=False)
    op.create_index("ix_payments_tx_ref", "payments", ["tx_ref"], unique=False)
    op.create_index("ix_payments_gateway_event", "payments", ["gateway_event_id"], unique=False)
    op.create_index("ix_payments_card_fingerprint", "payments", ["card_fingerprint"], unique=False)


# ─────────────────────────────────────────────────────────────────────
# Admin control panel, task execution & chargeback (PRD §6, §6a, §12)
# ─────────────────────────────────────────────────────────────────────


def _create_verification_tasks():
    op.create_table(
        "verification_tasks",
        sa.Column("verification_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("tier", sa.String(length=16), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False, server_default="PENDING"),
        sa.Column("assigned_agent_id", sa.String(length=36), nullable=True),
        sa.Column("assignment_mode", sa.String(length=16), nullable=True),
        sa.Column("in_pool", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("pool_expires_at", UTCDateTime, nullable=True),
        sa.Column("accept_deadline_at", UTCDateTime, nullable=True),
        sa.Column("decline_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("remote_bonus_minor", sa.BigInteger(), nullable=True),
        sa.Column("assigned_at", UTCDateTime, nullable=True),
        sa.Column("accepted_at", UTCDateTime, nullable=True),
        sa.Column("submitted_at", UTCDateTime, nullable=True),
        sa.Column("approved_at", UTCDateTime, nullable=True),
        # Role-specific findings captured on submit (§12.2); rejection feedback on rework.
        sa.Column("submission_payload", JSONB_VARIANT, nullable=True),
        sa.Column("rejection_reason", sa.String(length=1000), nullable=True),
        # Admin review outcome + per-task quality for the composite trust score (§8.3).
        sa.Column("review_decision", sa.String(length=16), nullable=True),
        sa.Column("review_quality", sa.Integer(), nullable=False, server_default="100"),
        # Optional customer-facing interim reassurance note, set on approval (§9.3).
        sa.Column("interim_note", sa.String(length=280), nullable=True),
        *AlembicUtils.base_audit_columns(),
        # A verification has at most one task per role; rework reuses the row.
        sa.UniqueConstraint("verification_id", "role", name="uq_verification_tasks_role"),
    )
    op.create_index("ix_verification_tasks_id", "verification_tasks", ["id"], unique=True)
    op.create_index("ix_verification_tasks_verification_id", "verification_tasks", ["verification_id"], unique=False)
    op.create_index("ix_verification_tasks_state", "verification_tasks", ["state"], unique=False)
    op.create_index("ix_verification_tasks_agent", "verification_tasks", ["assigned_agent_id"], unique=False)


def _create_commissions():
    op.create_table(
        "commissions",
        sa.Column("verification_id", sa.String(length=36), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=True),
        sa.Column("agent_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("tier", sa.String(length=16), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="NGN"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="CLEARING"),
        sa.Column("clearing_until", UTCDateTime, nullable=True),
        sa.Column("reserve_amount_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("reserve_until", UTCDateTime, nullable=True),
        sa.Column("reserve_released_at", UTCDateTime, nullable=True),
        sa.Column("frozen_from_status", sa.String(length=16), nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_commissions_id", "commissions", ["id"], unique=True)
    op.create_index("ix_commissions_verification", "commissions", ["verification_id"], unique=False)
    op.create_index("ix_commissions_agent", "commissions", ["agent_id"], unique=False)
    op.create_index("ix_commissions_status", "commissions", ["status"], unique=False)


def _create_chargebacks():
    op.create_table(
        "chargebacks",
        sa.Column("payment_id", sa.String(length=36), nullable=False),
        sa.Column("verification_id", sa.String(length=36), nullable=False),
        sa.Column("gateway_event_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="FLAGGED"),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="NGN"),
        sa.Column("rebuttal_pack", JSONB_VARIANT, nullable=True),
        sa.Column("resolved_at", UTCDateTime, nullable=True),
        *AlembicUtils.base_audit_columns(),
        # Idempotency key so a replayed chargeback webhook is a no-op (§4.6).
        sa.UniqueConstraint("gateway_event_id", name="uq_chargebacks_gateway_event"),
    )
    op.create_index("ix_chargebacks_id", "chargebacks", ["id"], unique=True)
    op.create_index("ix_chargebacks_payment", "chargebacks", ["payment_id"], unique=False)
    op.create_index("ix_chargebacks_verification", "chargebacks", ["verification_id"], unique=False)
    op.create_index("ix_chargebacks_status", "chargebacks", ["status"], unique=False)


def _create_admin_notes():
    op.create_table(
        "admin_notes",
        sa.Column("verification_id", sa.String(length=36), nullable=False),
        sa.Column("author_id", sa.String(length=36), nullable=False),
        sa.Column("category", sa.String(length=16), nullable=False, server_default="OPERATIONAL"),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default="false"),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_admin_notes_id", "admin_notes", ["id"], unique=True)
    op.create_index("ix_admin_notes_verification", "admin_notes", ["verification_id"], unique=False)


def _create_task_evidence():
    op.create_table(
        "task_evidence",
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("verification_id", sa.String(length=36), nullable=False),
        sa.Column("agent_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="PHOTO"),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("storage_url", sa.String(length=1024), nullable=True),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        # §4.5 content hash + §12.3 server-set proof-of-presence.
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("gps_latitude", sa.Float(), nullable=True),
        sa.Column("gps_longitude", sa.Float(), nullable=True),
        sa.Column("captured_at", UTCDateTime, nullable=True),
        sa.Column("uploaded_at", UTCDateTime, nullable=False),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_task_evidence_id", "task_evidence", ["id"], unique=True)
    op.create_index("ix_task_evidence_task", "task_evidence", ["task_id"], unique=False)
    op.create_index("ix_task_evidence_verification", "task_evidence", ["verification_id"], unique=False)


def _create_trust_score_weight_config():
    op.create_table(
        "trust_score_weight_config",
        sa.Column("tier", sa.String(length=16), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("weight_percent", sa.Integer(), nullable=False, server_default="0"),
        *AlembicUtils.base_audit_columns(),
        # One weight per (tier, role); weights sum to 100 within a tier (app-enforced).
        sa.UniqueConstraint("tier", "role", name="uq_trust_weight_tier_role"),
    )
    op.create_index("ix_trust_score_weight_config_id", "trust_score_weight_config", ["id"], unique=True)


def _create_reports():
    op.create_table(
        "reports",
        sa.Column("verification_id", sa.String(length=36), nullable=False),
        sa.Column("report_version", sa.Integer(), nullable=False, server_default="1"),
        # Semantic version label + why the version was produced (§10.1 / §14).
        sa.Column("version_label", sa.String(length=12), nullable=False, server_default="1.0"),
        sa.Column("revision_kind", sa.String(length=16), nullable=False, server_default="INITIAL"),
        sa.Column("state", sa.String(length=16), nullable=False, server_default="DRAFT"),
        sa.Column("composite_trust_score", sa.Integer(), nullable=True),
        sa.Column("findings", JSONB_VARIANT, nullable=True),
        sa.Column("release_reason", sa.String(length=1000), nullable=True),
        sa.Column("released_by", sa.String(length=36), nullable=True),
        sa.Column("released_at", UTCDateTime, nullable=True),
        sa.Column("superseded_at", UTCDateTime, nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_reports_id", "reports", ["id"], unique=True)
    op.create_index("ix_reports_verification", "reports", ["verification_id"], unique=False)
    op.create_index("ix_reports_state", "reports", ["state"], unique=False)


def _create_conversations():
    # Communication threads (§11.1): one per verification per channel + per-user general support.
    op.create_table(
        "conversations",
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("verification_id", sa.String(length=36), nullable=True),
        sa.Column("subject", sa.String(length=200), nullable=True),
        sa.Column("last_message_at", UTCDateTime, nullable=True),
        sa.Column("closed", sa.Boolean(), nullable=False, server_default="false"),
        # ``created_by`` (thread opener) comes from base_audit_columns.
        *AlembicUtils.base_audit_columns(),
        # Folded columns trail the audit block so a freshly built database matches one
        # migrated through the original chain column-for-column (ADD COLUMN appends).
        # folded from 0002_whatsapp_channel — source labeling, so a WhatsApp thread is
        # distinguishable in the admin console without becoming a separate pipeline.
        sa.Column("channel", sa.String(length=10), nullable=False, server_default=_CHANNEL_WEB),
        # The sender's E.164 number for a WhatsApp thread — how an inbound message finds its
        # existing thread before the number is linked to an account.
        sa.Column("external_ref", sa.String(length=20), nullable=True),
    )
    op.create_index("ix_conversations_id", "conversations", ["id"], unique=True)
    op.create_index("ix_conversations_verification", "conversations", ["verification_id"], unique=False)
    op.create_index("ix_conversations_external_ref", "conversations", ["external_ref"], unique=False)


def _create_conversation_participants():
    # Per-user membership + read state — backs the Chat unread counter (§N.3).
    op.create_table(
        "conversation_participants",
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=True),
        sa.Column("last_read_at", UTCDateTime, nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_conv_participants_id", "conversation_participants", ["id"], unique=True)
    op.create_index("ix_conv_participants_user", "conversation_participants", ["user_id"], unique=False)
    op.create_index(
        "ix_conv_participants_conversation", "conversation_participants", ["conversation_id"], unique=False
    )


def _create_chat_messages():
    # In-app messages + the §4.7 fraud-hold state machine.
    op.create_table(
        "chat_messages",
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("sender_user_id", sa.String(length=36), nullable=True),
        sa.Column("sender_kind", sa.String(length=16), nullable=False, server_default="SYSTEM"),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=True),
        sa.Column("state", sa.String(length=20), nullable=False, server_default="PENDING_SCAN"),
        sa.Column("message_kind", sa.String(length=24), nullable=False, server_default="CHAT"),
        sa.Column("clarification_status", sa.String(length=16), nullable=True),
        sa.Column("flagged_categories", JSONB_VARIANT, nullable=True),
        sa.Column("attachments", JSONB_VARIANT, nullable=True),
        sa.Column("delivered_at", UTCDateTime, nullable=True),
        sa.Column("held_at", UTCDateTime, nullable=True),
        sa.Column("reviewed_by", sa.String(length=36), nullable=True),
        sa.Column("reviewed_at", UTCDateTime, nullable=True),
        *AlembicUtils.base_audit_columns(),
        # Folded columns trail the audit block — see `_create_conversations`.
        # folded from 0002_whatsapp_channel — which surface the message came from.
        sa.Column("source", sa.String(length=10), nullable=False, server_default=_SOURCE_WEB),
        sa.Column("external_message_id", sa.String(length=128), nullable=True),
        # folded from 0007_chat_channel_delivery. Deliberately **not** a reuse of
        # ``delivered_at``, which means "released past the §4.7 fraud hold": conflating the
        # two would make a held message look channel-delivered, and a message queued outside
        # Meta's 24-hour window look lost. Null on an admin/agent message in a WhatsApp
        # thread is what marks it as still waiting to go out.
        sa.Column("channel_delivered_at", UTCDateTime, nullable=True),
        # What a non-text inbound actually was (§26.6.3), so the console can flag an image as
        # unofficial and a voice note as audio without joining back to
        # ``whatsapp_inbound_messages`` for every row it renders.
        sa.Column("media_kind", sa.String(length=16), nullable=True),
    )
    op.create_index("ix_chat_messages_id", "chat_messages", ["id"], unique=True)
    op.create_index("ix_chat_messages_conversation", "chat_messages", ["conversation_id"], unique=False)
    op.create_index("ix_chat_messages_task", "chat_messages", ["task_id"], unique=False)
    op.create_index("ix_chat_messages_state", "chat_messages", ["state"], unique=False)
    # The queue read is "this thread's undelivered agent replies", so the index is on the
    # pair rather than on the timestamp alone.
    op.create_index(
        "ix_chat_messages_channel_pending", "chat_messages", ["conversation_id", "channel_delivered_at"]
    )


def _create_notifications():
    # In-app system notifications (§12, §N.4).
    op.create_table(
        "notifications",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("link", sa.String(length=300), nullable=True),
        sa.Column("read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("event_ref", sa.String(length=36), nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_notifications_id", "notifications", ["id"], unique=True)
    op.create_index("ix_notifications_user", "notifications", ["user_id"], unique=False)


def _create_notification_preferences():
    # Per-user, per-event email/SMS opt-out (§12.4). In-app is never disableable.
    op.create_table(
        "notification_preferences",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sms_enabled", sa.Boolean(), nullable=False, server_default="true"),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_notif_prefs_id", "notification_preferences", ["id"], unique=True)
    op.create_index("ix_notif_prefs_user", "notification_preferences", ["user_id"], unique=False)


def _create_verification_shares():
    # Tokenised, revocable, time-limited report shares (§13.2).
    op.create_table(
        "verification_shares",
        sa.Column("verification_id", sa.String(length=36), nullable=False),
        sa.Column("share_type", sa.String(length=16), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("recipient_email", sa.String(length=254), nullable=True),
        sa.Column("expires_at", UTCDateTime, nullable=True),
        sa.Column("revoked_at", UTCDateTime, nullable=True),
        sa.Column("first_viewed_at", UTCDateTime, nullable=True),
        sa.Column("disclaimer_acked_at", UTCDateTime, nullable=True),
        *AlembicUtils.base_audit_columns(),
        sa.UniqueConstraint("token", name="uq_verification_shares_token"),
    )
    op.create_index("ix_verification_shares_id", "verification_shares", ["id"], unique=True)
    op.create_index(
        "ix_verification_shares_verification", "verification_shares", ["verification_id"], unique=False
    )
    op.create_index("ix_verification_shares_token", "verification_shares", ["token"], unique=False)


def _create_recheck_requests():
    # Customer re-check requests (§14.1).
    op.create_table(
        "recheck_requests",
        sa.Column("verification_id", sa.String(length=36), nullable=False),
        sa.Column("customer_id", sa.String(length=36), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("documents", JSONB_VARIANT, nullable=True),
        sa.Column("scope_roles", JSONB_VARIANT, nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="PENDING"),
        sa.Column("price_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("payment_id", sa.String(length=36), nullable=True),
        sa.Column("decision_note", sa.String(length=1000), nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_recheck_requests_id", "recheck_requests", ["id"], unique=True)
    op.create_index("ix_recheck_verification", "recheck_requests", ["verification_id"], unique=False)
    op.create_index("ix_recheck_requests_status", "recheck_requests", ["status"], unique=False)
    op.create_index("ix_recheck_requests_payment", "recheck_requests", ["payment_id"], unique=False)


def _create_upgrade_requests():
    # Customer tier-upgrade requests (§14.2).
    op.create_table(
        "upgrade_requests",
        sa.Column("verification_id", sa.String(length=36), nullable=False),
        sa.Column("customer_id", sa.String(length=36), nullable=False),
        sa.Column("from_tier", sa.String(length=16), nullable=False),
        sa.Column("to_tier", sa.String(length=16), nullable=False),
        sa.Column("delta_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="PENDING"),
        sa.Column("payment_id", sa.String(length=36), nullable=True),
        sa.Column("idempotency_key", sa.String(length=80), nullable=False),
        *AlembicUtils.base_audit_columns(),
        sa.UniqueConstraint("idempotency_key", name="uq_upgrade_requests_key"),
    )
    op.create_index("ix_upgrade_requests_id", "upgrade_requests", ["id"], unique=True)
    op.create_index("ix_upgrade_verification", "upgrade_requests", ["verification_id"], unique=False)
    op.create_index("ix_upgrade_requests_status", "upgrade_requests", ["status"], unique=False)
    op.create_index("ix_upgrade_requests_payment", "upgrade_requests", ["payment_id"], unique=False)


def _create_disputes():
    # Customer disputes + admin-mediated agent defence + resolution (§14.3).
    op.create_table(
        "disputes",
        sa.Column("verification_id", sa.String(length=36), nullable=False),
        sa.Column("customer_id", sa.String(length=36), nullable=False),
        sa.Column("dispute_type", sa.String(length=24), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("evidence", JSONB_VARIANT, nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="OPEN"),
        sa.Column("target_role", sa.String(length=16), nullable=True),
        sa.Column("agent_id", sa.String(length=36), nullable=True),
        sa.Column("agent_defence_text", sa.Text(), nullable=True),
        sa.Column("agent_defence_at", UTCDateTime, nullable=True),
        sa.Column("resolution_outcome", sa.String(length=24), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("resolved_by", sa.String(length=36), nullable=True),
        sa.Column("resolved_at", UTCDateTime, nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_disputes_id", "disputes", ["id"], unique=True)
    op.create_index("ix_disputes_verification", "disputes", ["verification_id"], unique=False)
    op.create_index("ix_disputes_status", "disputes", ["status"], unique=False)
    op.create_index("ix_disputes_agent", "disputes", ["agent_id"], unique=False)


def _create_system_config():
    # Admin-editable operational config for §14 (dispute window, re-check pricing, …) — D28.
    op.create_table(
        "system_config",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value_json", JSONB_VARIANT, nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        *AlembicUtils.base_audit_columns(),
        sa.UniqueConstraint("key", name="uq_system_config_key"),
    )
    op.create_index("ix_system_config_id", "system_config", ["id"], unique=True)
    op.create_index("ix_system_config_key", "system_config", ["key"], unique=False)


def _create_commission_rules():
    # Admin per-role×tier agent commission rates in basis points (§15.1 / D30).
    op.create_table(
        "commission_rules",
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("tier", sa.String(length=16), nullable=False),
        sa.Column("rate_bps", sa.Integer(), nullable=False, server_default="0"),
        *AlembicUtils.base_audit_columns(),
        sa.UniqueConstraint("role", "tier", name="uq_commission_rule_role_tier"),
    )
    op.create_index("ix_commission_rules_id", "commission_rules", ["id"], unique=True)


def _create_agent_bank_accounts():
    # Stored payout beneficiaries for an agent (§15.1).
    op.create_table(
        "agent_bank_accounts",
        sa.Column("agent_id", sa.String(length=36), nullable=False),
        sa.Column("bank_name", sa.String(length=128), nullable=False),
        sa.Column("account_number", sa.String(length=32), nullable=False),
        sa.Column("account_name", sa.String(length=128), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_agent_bank_accounts_id", "agent_bank_accounts", ["id"], unique=True)
    op.create_index("ix_agent_bank_accounts_agent", "agent_bank_accounts", ["agent_id"], unique=False)


def _create_payouts():
    # Agent withdrawals of cleared earnings; Finance approve/hold/adjust/reject (§15.1).
    op.create_table(
        "payouts",
        sa.Column("agent_id", sa.String(length=36), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="NGN"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="REQUESTED"),
        sa.Column("bank_name", sa.String(length=128), nullable=False),
        sa.Column("account_number", sa.String(length=32), nullable=False),
        sa.Column("account_name", sa.String(length=128), nullable=False),
        sa.Column("requested_at", UTCDateTime, nullable=True),
        sa.Column("sla_due_at", UTCDateTime, nullable=True),
        sa.Column("decided_at", UTCDateTime, nullable=True),
        sa.Column("decided_by", sa.String(length=36), nullable=True),
        sa.Column("adjustment_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("note", sa.Text(), nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_payouts_id", "payouts", ["id"], unique=True)
    op.create_index("ix_payouts_agent", "payouts", ["agent_id"], unique=False)
    op.create_index("ix_payouts_status", "payouts", ["status"], unique=False)


def _create_pricing_tier_config():
    # Admin-editable per-tier NGN price (§18.1 / D36, S22). Replaces the hardcoded dict.
    op.create_table(
        "pricing_tier_config",
        sa.Column("tier", sa.String(length=16), nullable=False),
        sa.Column("price_ngn_kobo", sa.BigInteger(), nullable=False),
        *AlembicUtils.base_audit_columns(),
        sa.UniqueConstraint("tier", name="uq_pricing_tier_config_tier"),
    )
    op.create_index("ix_pricing_tier_config_id", "pricing_tier_config", ["id"], unique=True)
    op.create_index("ix_pricing_tier_config_tier", "pricing_tier_config", ["tier"], unique=False)


def _create_pricing_line_items():
    # Itemized per-tier price breakdown (§5.2 / §18.1, S22).
    op.create_table(
        "pricing_line_items",
        sa.Column("tier", sa.String(length=16), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_pricing_line_items_id", "pricing_line_items", ["id"], unique=True)
    op.create_index("ix_pricing_line_items_tier", "pricing_line_items", ["tier"], unique=False)


def _create_broadcasts():
    # Admin announcements to an audience — send-now or scheduled (§18.1 / D37, S22).
    op.create_table(
        "broadcasts",
        sa.Column("audience", sa.String(length=16), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="DRAFT"),
        sa.Column("scheduled_at", UTCDateTime, nullable=True),
        sa.Column("sent_at", UTCDateTime, nullable=True),
        sa.Column("recipient_count", sa.Integer(), nullable=False, server_default="0"),
        # created_by is provided by base_audit_columns() (inherited from BaseEntity).
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_broadcasts_id", "broadcasts", ["id"], unique=True)
    op.create_index("ix_broadcasts_status", "broadcasts", ["status"], unique=False)
    op.create_index("ix_broadcasts_created_by", "broadcasts", ["created_by"], unique=False)


def _create_referrals():
    # A user's shareable referral link/code (§17.1, S21).
    op.create_table(
        "referrals",
        sa.Column("referrer_user_id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        *AlembicUtils.base_audit_columns(),
        sa.UniqueConstraint("referrer_user_id", name="uq_referrals_referrer"),
        sa.UniqueConstraint("code", name="uq_referrals_code"),
    )
    op.create_index("ix_referrals_id", "referrals", ["id"], unique=True)
    op.create_index("ix_referrals_referrer", "referrals", ["referrer_user_id"], unique=False)
    op.create_index("ix_referrals_code", "referrals", ["code"], unique=False)


def _create_referral_credits():
    # Referral-credit ledger — PENDING until the invitee's payment clears the chargeback
    # window, then CLEARED to the referrer's balance (§17.1 / D35, S21).
    op.create_table(
        "referral_credits",
        sa.Column("referrer_user_id", sa.String(length=36), nullable=False),
        sa.Column("invitee_user_id", sa.String(length=36), nullable=False),
        sa.Column("verification_id", sa.String(length=36), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="PENDING"),
        sa.Column("clearing_until", UTCDateTime, nullable=True),
        sa.Column("cleared_at", UTCDateTime, nullable=True),
        sa.Column("void_reason", sa.String(length=64), nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_referral_credits_id", "referral_credits", ["id"], unique=True)
    op.create_index("ix_referral_credits_referrer", "referral_credits", ["referrer_user_id"], unique=False)
    op.create_index("ix_referral_credits_invitee", "referral_credits", ["invitee_user_id"], unique=False)
    op.create_index("ix_referral_credits_verification", "referral_credits", ["verification_id"], unique=False)
    op.create_index("ix_referral_credits_status", "referral_credits", ["status"], unique=False)


def _create_report_acknowledgements():
    # Customer access-gate acknowledgement, recorded against the report version (§10.1).
    op.create_table(
        "report_acknowledgements",
        sa.Column("verification_id", sa.String(length=36), nullable=False),
        sa.Column("report_id", sa.String(length=36), nullable=False),
        sa.Column("report_version", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.String(length=36), nullable=False),
        sa.Column("acknowledged_at", UTCDateTime, nullable=False),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_report_ack_id", "report_acknowledgements", ["id"], unique=True)
    op.create_index("ix_report_ack_verification", "report_acknowledgements", ["verification_id"], unique=False)
    op.create_index("ix_report_ack_customer", "report_acknowledgements", ["customer_id"], unique=False)


# ─────────────────────────────────────────────────────────────────────
# WhatsApp channel (PRD §26; orig: 0002_whatsapp_channel … 0010_whatsapp_channel_analytics)
#
# A second thin surface over the same backend, not a second backend: no case
# state lives here. The tables hold the channel's own bookkeeping — the inbound
# journal, the identity seam, bot state, consent, delegates, and the §26.10
# fact table.
# ─────────────────────────────────────────────────────────────────────


def _create_whatsapp_inbound_messages():
    # The journal every Meta delivery lands in (§26.1).
    op.create_table(
        "whatsapp_inbound_messages",
        sa.Column("wamid", sa.String(length=128), nullable=False),
        sa.Column("from_phone", sa.String(length=20), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("interactive_id", sa.String(length=64), nullable=True),
        sa.Column("media_id", sa.String(length=128), nullable=True),
        sa.Column("media_mime_type", sa.String(length=100), nullable=True),
        sa.Column("sender_name", sa.String(length=120), nullable=True),
        sa.Column("payload", JSONB_VARIANT, nullable=True),
        sa.Column("received_at", UTCDateTime, nullable=True),
        sa.Column("processed_at", UTCDateTime, nullable=True),
        sa.Column("chat_message_id", sa.String(length=36), nullable=True),
        *AlembicUtils.base_audit_columns(),
        # Folded columns trail the audit block — see `_create_conversations`.
        # folded from 0010_whatsapp_channel_analytics — the widget's `[ref: …]` marker (D85),
        # lifted out of the message text at ingest.
        sa.Column("page_code", sa.String(length=40), nullable=True),
    )
    op.create_index("ix_whatsapp_inbound_messages_id", "whatsapp_inbound_messages", ["id"], unique=True)
    op.create_index("ix_whatsapp_inbound_from_phone", "whatsapp_inbound_messages", ["from_phone"], unique=False)
    op.create_index(
        "ix_whatsapp_inbound_messages_chat_message_id",
        "whatsapp_inbound_messages", ["chat_message_id"], unique=False,
    )
    # §26.10's voice-note volume is counted over a window off this table.
    op.create_index("ix_whatsapp_inbound_kind_received", "whatsapp_inbound_messages", ["kind", "received_at"])
    # Exactly-once ingestion: a Meta redelivery collides here instead of producing a
    # duplicate conversation turn.
    op.create_unique_constraint("uq_whatsapp_inbound_wamid", "whatsapp_inbound_messages", ["wamid"])


def _create_handoff_token_redemptions():
    # The §26.5 handoff token is stateless (a signed RS256 JWT); this table is what makes it
    # single-use — redemption claims the token's `jti` and the unique constraint is the
    # enforcement, so two concurrent redemptions of a forwarded link race and one wins.
    op.create_table(
        "handoff_token_redemptions",
        sa.Column("jti", sa.String(length=64), nullable=False),
        sa.Column("intent", sa.String(length=10), nullable=False),
        # Nullable (folded from 0004_whatsapp_linking): a `link` or `intake` token names a
        # phone number instead of a case (D55/D71).
        sa.Column("case_id", sa.String(length=36), nullable=True),
        sa.Column("customer_id", sa.String(length=36), nullable=True),
        sa.Column("redeemed_at", UTCDateTime, nullable=False),
        # Which client actually burned the link — the §26.11 pen-check trail.
        sa.Column("redeemed_ip", sa.String(length=45), nullable=True),
        *AlembicUtils.base_audit_columns(),
        # Folded columns trail the audit block — see `_create_conversations`.
        # folded from 0004_whatsapp_linking — the phone a phone-scoped token names.
        sa.Column("phone_e164", sa.String(length=32), nullable=True),
    )
    op.create_index("ix_handoff_token_redemptions_id", "handoff_token_redemptions", ["id"], unique=True)
    # Single-use enforcement: a replayed nonce collides here.
    op.create_unique_constraint("uq_handoff_token_redemptions_jti", "handoff_token_redemptions", ["jti"])


def _create_whatsapp_links():
    # The channel's identity seam (§26.4.4): one row per account, one number per row.
    op.create_table(
        "whatsapp_links",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        # Null once revoked, which is what releases the number for another account.
        sa.Column("phone_e164", sa.String(length=32), nullable=True),
        sa.Column("wa_id", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=10), nullable=False, server_default=_STATUS_PENDING),
        sa.Column("linked_at", UTCDateTime, nullable=True),
        sa.Column("revoked_at", UTCDateTime, nullable=True),
        sa.Column("revoked_reason", sa.String(length=120), nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_whatsapp_links_id", "whatsapp_links", ["id"], unique=True)
    # The §26.4.4 one-to-one rule, enforced in the database rather than by convention.
    op.create_unique_constraint("uq_whatsapp_links_user_id", "whatsapp_links", ["user_id"])
    op.create_unique_constraint("uq_whatsapp_links_phone_e164", "whatsapp_links", ["phone_e164"])


def _create_whatsapp_templates():
    # Only what Meta owns — review status, their id, a rejection reason. The §26.7 template
    # *definitions* are code-owned (D59), because the code is what fills their parameters.
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


def _create_whatsapp_bot_sessions():
    # One row per number: where the conversation is, whether a human has taken it over, and
    # how many turns in a row the bot has failed to understand (§26.3.3, §26.6).
    op.create_table(
        "whatsapp_bot_sessions",
        # E.164 with the leading '+', matching `whatsapp_links.phone_e164` and the
        # conversation's `external_ref`.
        sa.Column("phone_e164", sa.String(length=32), nullable=False),
        sa.Column("mode", sa.String(length=10), nullable=False, server_default=_MODE_BOT),
        sa.Column("mode_changed_at", UTCDateTime, nullable=True),
        sa.Column("current_flow", sa.String(length=24), nullable=True),
        sa.Column("step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("context", JSONB_VARIANT, nullable=True),
        sa.Column("last_inbound_at", UTCDateTime, nullable=True),
        sa.Column("welcomed_at", UTCDateTime, nullable=True),
        sa.Column("unmatched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_escalation_reason", sa.String(length=32), nullable=True),
        sa.Column("last_escalated_at", UTCDateTime, nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_whatsapp_bot_sessions_id", "whatsapp_bot_sessions", ["id"], unique=True)
    # One session per number: two rows would mean two half-remembered conversations
    # with one person, and the sticky-HUMAN rule would hold on only one of them.
    op.create_unique_constraint(
        "uq_whatsapp_bot_sessions_phone_e164", "whatsapp_bot_sessions", ["phone_e164"]
    )


def _create_whatsapp_consents():
    # The §26.4.6 opt-in ledger the notification router enforces (D63). Each consent keeps a
    # grant *and* a revoke timestamp and no boolean: §26.8 wants the record timestamped and
    # exportable, so the pair of stamps *is* the record and a flag beside them could only
    # drift from the evidence justifying it.
    op.create_table(
        "whatsapp_consents",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        # "Send me progress updates about this verification on WhatsApp" (§26.4.6 #1).
        sa.Column("utility_granted_at", UTCDateTime, nullable=True),
        sa.Column("utility_revoked_at", UTCDateTime, nullable=True),
        sa.Column("utility_source", sa.String(length=24), nullable=True),
        # "Send me occasional Veriprops news and offers on WhatsApp" (§26.4.6 #2).
        sa.Column("marketing_granted_at", UTCDateTime, nullable=True),
        sa.Column("marketing_revoked_at", UTCDateTime, nullable=True),
        sa.Column("marketing_source", sa.String(length=24), nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_whatsapp_consents_id", "whatsapp_consents", ["id"], unique=True)
    # One consent state per account: two concurrent captures must not leave the router
    # choosing between two answers to the same question.
    op.create_unique_constraint("uq_whatsapp_consents_user_id", "whatsapp_consents", ["user_id"])


def _create_case_delegates():
    # The §26.4.5 per-case, status-only, revocable grant (D67). The number lives here rather
    # than in `whatsapp_links`: a delegate has no account, so reusing the link table would
    # break its one-account-one-number constraints or hand a delegate an account identity.
    op.create_table(
        "case_delegates",
        sa.Column("verification_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("phone_e164", sa.String(length=32), nullable=False),
        # Null until the OTP is confirmed — nothing is visible before that moment.
        sa.Column("verified_at", UTCDateTime, nullable=True),
        sa.Column("revoked_at", UTCDateTime, nullable=True),
        sa.Column("revoked_reason", sa.String(length=120), nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_case_delegates_id", "case_delegates", ["id"], unique=True)
    # The two lookups: the buyer's case page, and the bot resolving an inbound number.
    op.create_index("ix_case_delegates_verification", "case_delegates", ["verification_id"])
    op.create_index("ix_case_delegates_phone", "case_delegates", ["phone_e164"])
    # §26.4.5's one-delegate-per-case rule, enforced in the database over *live* rows only.
    # A plain unique constraint would make the first revocation permanent.
    op.create_index(
        "uq_case_delegates_live_per_case",
        "case_delegates",
        ["verification_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL AND deleted = false"),
    )


def _create_whatsapp_channel_events():
    # The §26.10 append-only fact table (D80). Four of the seven metrics are *rates over a
    # window*, which the channel's operational tables cannot answer: they hold one mutated
    # row per number, so a finished intake reads identically to one that never started.
    op.create_table(
        "whatsapp_channel_events",
        # When the thing happened, which is not always when the row was written: a fact
        # recorded from an event subscriber lags its cause. Every metric windows on this.
        sa.Column("occurred_at", UTCDateTime, nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("phone_e164", sa.String(length=32), nullable=True),
        # Free text, not an enum: the codes name frontend routes the backend does not
        # model, and the widget derives one for any new page without a table edit.
        sa.Column("page_code", sa.String(length=40), nullable=True),
        sa.Column("reason", sa.String(length=32), nullable=True),
        sa.Column("verification_id", sa.String(length=36), nullable=True),
        sa.Column("customer_id", sa.String(length=36), nullable=True),
        sa.Column("detail", JSONB_VARIANT, nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_whatsapp_channel_events_id", "whatsapp_channel_events", ["id"], unique=True)
    # Every §26.10 metric is "rows of this type in this window", so the composite index is
    # the access path rather than an optimisation.
    op.create_index(
        "ix_whatsapp_channel_events_type_time", "whatsapp_channel_events", ["event_type", "occurred_at"]
    )
    # Seam conversion asks "has this channel touched this case?" once per confirmed
    # payment on the whole platform, so it must not be a scan.
    op.create_index(
        "ix_whatsapp_channel_events_verification", "whatsapp_channel_events", ["verification_id"]
    )


def _create_whatsapp_number_health():
    # Meta's quality rating for our sending number (D81), cached in the same posture as the
    # §26.7 template registry: their verdict, our timestamp, and nothing in the send path
    # ever reads it.
    op.create_table(
        "whatsapp_number_health",
        sa.Column("phone_number_id", sa.String(length=64), nullable=False),
        # Defaults to UNKNOWN rather than GREEN: the state before a first successful sync
        # must never read as a clean bill of health.
        sa.Column("quality_rating", sa.String(length=16), nullable=False, server_default=_QUALITY_UNKNOWN),
        # Meta's vocabulary, which they extend without notice — an enum here would turn a
        # new tier into a sync failure.
        sa.Column("messaging_limit_tier", sa.String(length=32), nullable=True),
        sa.Column("last_synced_at", UTCDateTime, nullable=True),
        # Kept rather than raised, so the admin surface can say "showing GREEN, but we
        # have not been able to ask since Tuesday".
        sa.Column("sync_error", sa.String(length=255), nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_whatsapp_number_health_id", "whatsapp_number_health", ["id"], unique=True)
    op.create_index(
        "ix_whatsapp_number_health_phone_number_id", "whatsapp_number_health", ["phone_number_id"]
    )


# ─────────────────────────────────────────────────────────────────────
# Seed data — idempotent writers over pure row builders. The builders are
# the single translation point from the app-side registries to raw column
# values (enums reduced via ``.value``); ``test_migration_seed_parity``
# asserts they stay in lock-step with the registries, no DB needed.
# ─────────────────────────────────────────────────────────────────────


def _consent_document_rows() -> list[dict]:
    """One row per legal document in the content registry (§3.5)."""
    return [
        {
            "type": content.type.value,
            "consent_version": content.consent_version,
            "effective_at": content.effective_at,
            "title": content.title,
            "href": content.href,
            "body": content.body,
            "signoff_status": content.signoff_status.value,
        }
        for content in LEGAL_DOCUMENT_CONTENT.values()
    ]


def _trust_weight_rows() -> list[dict]:
    """One weight per (tier, role); weights sum to 100 within a tier (§8.3 / D14)."""
    return [
        {"tier": tier.value, "role": role.value, "weight_percent": weight}
        for tier, role_weights in DEFAULT_TRUST_WEIGHTS.items()
        for role, weight in role_weights.items()
    ]


def _system_config_rows() -> list[dict]:
    """One row per admin-tunable ConfigKey at its default value (§14 / D28)."""
    return [
        {
            "key": key.value,
            "value_json": json.dumps(default),
            "description": CONFIG_DESCRIPTIONS.get(key),
        }
        for key, default in CONFIG_DEFAULTS.items()
    ]


def _commission_rule_rows() -> list[dict]:
    """One rate per (role, tier), reproducing the prior flat model
    ``weight_percent/100 × AGENT_COMMISSION_SHARE`` in basis points (§15.1 / D30)."""
    return [
        {
            "role": role.value,
            "tier": tier.value,
            "rate_bps": round(weight * BPS_PER_PERCENT * settings.AGENT_COMMISSION_SHARE),
        }
        for tier, role_weights in DEFAULT_TRUST_WEIGHTS.items()
        for role, weight in role_weights.items()
    ]


def _pricing_tier_rows() -> list[dict]:
    """Default contractual NGN price per tier, in kobo (§18.1 / D36)."""
    return [
        {"tier": tier.value, "price_ngn_kobo": price}
        for tier, price in TIER_PRICE_NGN_KOBO.items()
    ]


def _pricing_line_item_rows() -> list[dict]:
    """One default line item per tier itemizing the full service fee (§5.2 / §18.1)."""
    return [
        {"tier": tier.value, "label": "Verification service fee",
         "amount_minor": price, "sort_order": 0}
        for tier, price in TIER_PRICE_NGN_KOBO.items()
    ]


def _seed_consent_documents() -> None:
    """Upsert every legal document by (type, consent_version): refresh the display
    fields on an existing row (backfills bodies on metadata-only databases), insert
    the full row otherwise."""
    conn = op.get_bind()
    now = Utils.datetime_now()
    for row in _consent_document_rows():
        existing = conn.execute(
            sa.text(
                "SELECT id FROM consent_documents "
                "WHERE type = :type AND consent_version = :consent_version LIMIT 1"
            ),
            {"type": row["type"], "consent_version": row["consent_version"]},
        ).first()
        if existing:
            conn.execute(
                sa.text(
                    "UPDATE consent_documents "
                    "SET title = :title, href = :href, body = :body, "
                    "signoff_status = :signoff_status, date_updated = :now "
                    "WHERE id = :id"
                ),
                {
                    "id": existing[0],
                    "title": row["title"],
                    "href": row["href"],
                    "body": row["body"],
                    "signoff_status": row["signoff_status"],
                    "now": now,
                },
            )
        else:
            conn.execute(
                sa.text(
                    "INSERT INTO consent_documents "
                    "(id, type, consent_version, effective_at, title, href, body, "
                    " signoff_status, date_created, deleted, version) "
                    "VALUES (:id, :type, :consent_version, :effective_at, :title, :href, "
                    "        :body, :signoff_status, :now, FALSE, 1)"
                ),
                {"id": Utils.generate_uuid(), "now": now, **row},
            )


def _seed_trust_score_weights() -> None:
    """Insert any missing default (tier, role) weight; never overwrites admin edits."""
    conn = op.get_bind()
    for row in _trust_weight_rows():
        existing = conn.execute(
            sa.text(
                "SELECT 1 FROM trust_score_weight_config "
                "WHERE tier = :tier AND role = :role LIMIT 1"
            ),
            {"tier": row["tier"], "role": row["role"]},
        ).first()
        if existing:
            continue
        conn.execute(
            sa.text(
                "INSERT INTO trust_score_weight_config "
                "(id, tier, role, weight_percent, date_created, deleted, version) "
                "VALUES (:id, :tier, :role, :weight_percent, :now, FALSE, 1)"
            ),
            {"id": Utils.generate_uuid(), "now": Utils.datetime_now(), **row},
        )


def _seed_system_config() -> None:
    """Insert any missing config key at its default value; never overwrites admin edits."""
    conn = op.get_bind()
    for row in _system_config_rows():
        existing = conn.execute(
            sa.text("SELECT 1 FROM system_config WHERE key = :key LIMIT 1"),
            {"key": row["key"]},
        ).first()
        if existing:
            continue
        conn.execute(
            sa.text(
                "INSERT INTO system_config "
                "(id, key, value_json, description, date_created, deleted, version) "
                "VALUES (:id, :key, :value_json, :description, :now, FALSE, 1)"
            ),
            {"id": Utils.generate_uuid(), "now": Utils.datetime_now(), **row},
        )


def _seed_commission_rules() -> None:
    """Insert any missing (role, tier) commission rate; never overwrites admin edits."""
    conn = op.get_bind()
    for row in _commission_rule_rows():
        existing = conn.execute(
            sa.text(
                "SELECT 1 FROM commission_rules "
                "WHERE role = :role AND tier = :tier LIMIT 1"
            ),
            {"role": row["role"], "tier": row["tier"]},
        ).first()
        if existing:
            continue
        conn.execute(
            sa.text(
                "INSERT INTO commission_rules "
                "(id, role, tier, rate_bps, date_created, deleted, version) "
                "VALUES (:id, :role, :tier, :rate_bps, :now, FALSE, 1)"
            ),
            {"id": Utils.generate_uuid(), "now": Utils.datetime_now(), **row},
        )


def _seed_pricing_defaults() -> None:
    """Insert any missing per-tier price row and default line item; never
    overwrites admin edits (the line-item check is soft-delete-aware, mirroring
    ``PricingLineItemRepo.list_for_tier``)."""
    conn = op.get_bind()
    for row in _pricing_tier_rows():
        existing = conn.execute(
            sa.text("SELECT 1 FROM pricing_tier_config WHERE tier = :tier LIMIT 1"),
            {"tier": row["tier"]},
        ).first()
        if existing:
            continue
        conn.execute(
            sa.text(
                "INSERT INTO pricing_tier_config "
                "(id, tier, price_ngn_kobo, date_created, deleted, version) "
                "VALUES (:id, :tier, :price_ngn_kobo, :now, FALSE, 1)"
            ),
            {"id": Utils.generate_uuid(), "now": Utils.datetime_now(), **row},
        )
    for row in _pricing_line_item_rows():
        existing = conn.execute(
            sa.text(
                "SELECT 1 FROM pricing_line_items "
                "WHERE tier = :tier AND deleted = FALSE LIMIT 1"
            ),
            {"tier": row["tier"]},
        ).first()
        if existing:
            continue
        conn.execute(
            sa.text(
                "INSERT INTO pricing_line_items "
                "(id, tier, label, amount_minor, sort_order, date_created, deleted, version) "
                "VALUES (:id, :tier, :label, :amount_minor, :sort_order, :now, FALSE, 1)"
            ),
            {"id": Utils.generate_uuid(), "now": Utils.datetime_now(), **row},
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


def _create_data_erasure_requests():
    # NDPA data-erasure requests + pseudonymisation trail (§18.1, §19.1, §4.11) — S23.
    op.create_table(
        "data_erasure_requests",
        sa.Column("subject_user_id", sa.String(length=36), nullable=False),
        sa.Column("requested_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="PENDING"),
        sa.Column("sla_due_at", UTCDateTime, nullable=True),
        sa.Column("reviewed_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("reviewed_at", UTCDateTime, nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("executed_at", UTCDateTime, nullable=True),
        sa.Column("pseudonym_token", sa.String(length=64), nullable=True),
        *AlembicUtils.base_audit_columns(),
    )
    op.create_index("ix_data_erasure_requests_id", "data_erasure_requests", ["id"], unique=True)
    op.create_index(
        "ix_data_erasure_requests_subject", "data_erasure_requests", ["subject_user_id"], unique=False
    )
    op.create_index(
        "ix_data_erasure_requests_status", "data_erasure_requests", ["status"], unique=False
    )


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
    ("devices", _create_devices),
    ("security_events", _create_security_events),
    ("password_reset_tokens", _create_password_reset_tokens),
    ("signup_drafts", _create_signup_drafts),
    ("messages", _create_messages),
    ("callbacks", _create_callbacks),
    ("audit_logs", _create_audit_logs),
    ("idempotency_keys", _create_idempotency_keys),
    ("agent_profiles", _create_agent_profiles),
    ("agent_credentials", _create_agent_credentials),
    ("agent_coverage", _create_agent_coverage),
    ("agent_application_drafts", _create_agent_application_drafts),
    ("admin_invitations", _create_admin_invitations),
    ("kyc_records", _create_kyc_records),
    ("properties", _create_properties),
    ("verifications", _create_verifications),
    ("payments", _create_payments),
    ("verification_tasks", _create_verification_tasks),
    ("commissions", _create_commissions),
    ("chargebacks", _create_chargebacks),
    ("admin_notes", _create_admin_notes),
    ("task_evidence", _create_task_evidence),
    ("trust_score_weight_config", _create_trust_score_weight_config),
    ("reports", _create_reports),
    ("verification_shares", _create_verification_shares),
    ("report_acknowledgements", _create_report_acknowledgements),
    ("conversations", _create_conversations),
    ("conversation_participants", _create_conversation_participants),
    ("chat_messages", _create_chat_messages),
    ("notifications", _create_notifications),
    ("notification_preferences", _create_notification_preferences),
    ("recheck_requests", _create_recheck_requests),
    ("upgrade_requests", _create_upgrade_requests),
    ("disputes", _create_disputes),
    ("system_config", _create_system_config),
    ("commission_rules", _create_commission_rules),
    ("agent_bank_accounts", _create_agent_bank_accounts),
    ("payouts", _create_payouts),
    ("referrals", _create_referrals),
    ("referral_credits", _create_referral_credits),
    ("pricing_tier_config", _create_pricing_tier_config),
    ("pricing_line_items", _create_pricing_line_items),
    ("broadcasts", _create_broadcasts),
    ("data_erasure_requests", _create_data_erasure_requests),
    # WhatsApp channel (§26). There are no foreign keys anywhere in this schema, so the
    # position of these entries is presentational rather than a dependency order.
    ("whatsapp_inbound_messages", _create_whatsapp_inbound_messages),
    ("handoff_token_redemptions", _create_handoff_token_redemptions),
    ("whatsapp_links", _create_whatsapp_links),
    ("whatsapp_templates", _create_whatsapp_templates),
    ("whatsapp_bot_sessions", _create_whatsapp_bot_sessions),
    ("whatsapp_consents", _create_whatsapp_consents),
    ("case_delegates", _create_case_delegates),
    ("whatsapp_channel_events", _create_whatsapp_channel_events),
    ("whatsapp_number_health", _create_whatsapp_number_health),
]


def upgrade() -> None:
    for name, builder in _TABLE_BUILDERS:
        if not AlembicUtils.table_exists(name):
            builder()

    # Reference-data seeds — the builder loop above guarantees every table
    # exists, and every writer is idempotent on an already-seeded database.
    _seed_consent_documents()
    _seed_super_admin()
    _seed_trust_score_weights()
    _seed_system_config()
    # Commission rates derive from the same weights map as the trust scores (D30).
    _seed_commission_rules()
    _seed_pricing_defaults()


def downgrade() -> None:
    for name, _builder in reversed(_TABLE_BUILDERS):
        if AlembicUtils.table_exists(name):
            op.drop_table(name)
