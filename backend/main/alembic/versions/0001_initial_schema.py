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
    ("audit_logs", _create_audit_logs),
    ("idempotency_keys", _create_idempotency_keys),
    ("agent_profiles", _create_agent_profiles),
    ("agent_credentials", _create_agent_credentials),
    ("agent_coverage", _create_agent_coverage),
    ("agent_application_drafts", _create_agent_application_drafts),
    ("admin_invitations", _create_admin_invitations),
    ("kyc_records", _create_kyc_records),
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


def downgrade() -> None:
    for name, _builder in reversed(_TABLE_BUILDERS):
        if AlembicUtils.table_exists(name):
            op.drop_table(name)
