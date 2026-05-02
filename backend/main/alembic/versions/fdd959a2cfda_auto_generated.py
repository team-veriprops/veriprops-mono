"""auto_generated

Revision ID: fdd959a2cfda
Revises: 
Create Date: 2025-06-01 02:19:26.646342

"""
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from passlib.context import CryptContext
from sqlalchemy import inspect as sa_inspect, JSON
from sqlalchemy.ext.mutable import MutableList

# revision identifiers, used by Alembic.
revision: str = 'fdd959a2cfda'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── helpers ────────────────────────────────────────────────────────


def _create_tab_key_values():
    op.create_table('key_values', sa.Column('key', sa.String(length=128), nullable=False),
                    sa.Column('value', sa.LargeBinary(), nullable=False),
                    sa.Column('expires_at', sa.DateTime(), nullable=False),
                    sa.PrimaryKeyConstraint('key'))
    op.create_index(op.f('ix_key_values_key'), 'key_values', ['key'], unique=True)


def _drop_tab_key_values():
    op.drop_index(op.f('ix_key_values_key'), table_name='key_values')
    op.drop_table('key_values')


def _base_audit_columns():
    """Mirror BaseEntity audit columns."""
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


def _create_signup_drafts():
    op.create_table(
        "signup_drafts",
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        *_base_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_signup_drafts_email"),
    )
    op.create_index("ix_signup_drafts_id", "signup_drafts", ["id"], unique=True)
    op.create_index("ix_signup_drafts_email", "signup_drafts", ["email"], unique=False)
    op.create_index("ix_signup_drafts_expires_at", "signup_drafts", ["expires_at"], unique=False)
    op.create_index(
        "ix_signup_drafts_email_active", "signup_drafts", ["email", "expires_at"], unique=False,
    )


def _drop_signup_drafts():
    op.drop_index("ix_signup_drafts_email_active", table_name="signup_drafts")
    op.drop_index("ix_signup_drafts_expires_at", table_name="signup_drafts")
    op.drop_index("ix_signup_drafts_email", table_name="signup_drafts")
    op.drop_index("ix_signup_drafts_id", table_name="signup_drafts")
    op.drop_constraint("uq_signup_drafts_email", "signup_drafts", type_="unique")
    op.drop_table("signup_drafts")

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
        sa.Column("personas", MutableList.as_mutable(JSON), nullable=False),
        sa.Column("admin_sub_role", sa.String(length=16), nullable=True),
        sa.Column("trust_status", sa.String(length=16), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("avatar_url", sa.String(length=512), nullable=True),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"),
        *_base_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email_normalized", name="uq_users_email"),
    )
    op.create_index("ix_users_phone_e164", "users", ["phone_e164"], unique=False)
    op.create_index("ix_users_deleted", "users", ["deleted"], unique=False)
    op.create_index("ix_users_id", "users", ["id"], unique=True)


def _drop_users():
    op.drop_index("ix_users_id", table_name="users")
    op.drop_index("ix_users_deleted", table_name="users")
    op.drop_index("ix_users_phone_e164", table_name="users")
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.drop_table("users")


def _create_oauth_identities():
    op.create_table(
        "oauth_identities",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("raw_profile", sa.Text(), nullable=True),
        *_base_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "subject", name="uq_oauth_provider_subject"),
    )
    op.create_index("ix_oauth_identities_id", "oauth_identities", ["id"], unique=True)
    op.create_index("ix_oauth_identities_user_id", "oauth_identities", ["user_id"], unique=False)


def _drop_oauth_identities():
    op.drop_index("ix_oauth_identities_user_id", table_name="oauth_identities")
    op.drop_index("ix_oauth_identities_id", table_name="oauth_identities")

    op.drop_constraint("uq_oauth_provider_subject", "oauth_identities", type_="unique")
    op.drop_table("oauth_identities")


def _create_consent_documents():
    op.create_table(
        "consent_documents",
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("consent_version", sa.String(length=16), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("href", sa.String(length=255), nullable=False),
        *_base_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("type", "consent_version", name="uq_consent_type_version"),
    )
    op.create_index("ix_consent_documents_type", "consent_documents", ["type"], unique=False)
    op.create_index("ix_consent_active_lookup", "consent_documents", ["type", "effective_at"], unique=False)
    op.create_index("ix_consent_documents_id", "consent_documents", ["id"], unique=True)


def _drop_consent_documents():
    op.drop_index("ix_consent_documents_id", table_name="consent_documents")
    op.drop_index("ix_consent_active_lookup", table_name="consent_documents")
    op.drop_index("ix_consent_documents_type", table_name="consent_documents")
    op.drop_table("consent_documents")


def _create_user_consents():
    op.create_table(
        "user_consents",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("document_type", sa.String(length=32), nullable=False),
        sa.Column("consent_version", sa.String(length=16), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("device_fingerprint", sa.String(length=128), nullable=True),
        *_base_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_consents_user_id", "user_consents", ["user_id"], unique=False)
    op.create_index("ix_user_consents_id", "user_consents", ["id"], unique=True)


def _drop_user_consents():
    op.drop_index("ix_user_consents_id", table_name="user_consents")
    op.drop_index("ix_user_consents_user_id", table_name="user_consents")
    op.drop_table("user_consents")


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
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        *_base_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("refresh_token_hash", name="uq_device_token_hash"),
    )
    op.create_index("ix_device_sessions_user_id", "device_sessions", ["user_id"], unique=False)
    op.create_index("ix_device_sessions_id", "device_sessions", ["id"], unique=True)


def _drop_device_sessions():
    op.drop_index("ix_device_sessions_id", table_name="device_sessions")
    op.drop_index("ix_device_sessions_user_id", table_name="device_sessions")

    op.drop_constraint("uq_device_token_hash", "device_sessions", type_="unique")
    op.drop_table("device_sessions")


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
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        *_base_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_security_events_user_id", "security_events", ["user_id"], unique=False)
    op.create_index("ix_security_events_type", "security_events", ["type"], unique=False)
    op.create_index("ix_security_events_occurred_at", "security_events", ["occurred_at"], unique=False)
    op.create_index("ix_security_events_id", "security_events", ["id"], unique=True)


def _drop_security_events():
    op.drop_index("ix_security_events_id", table_name="security_events")
    op.drop_index("ix_security_events_occurred_at", table_name="security_events")
    op.drop_index("ix_security_events_type", table_name="security_events")
    op.drop_index("ix_security_events_user_id", table_name="security_events")
    op.drop_table("security_events")


def _create_password_reset_tokens():
    op.create_table(
        "password_reset_tokens",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        *_base_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_password_reset_token_hash"),
    )
    op.create_index("ix_password_reset_user", "password_reset_tokens", ["user_id"], unique=False)
    op.create_index("ix_password_reset_tokens_id", "password_reset_tokens", ["id"], unique=True)


def _drop_password_reset_tokens():
    op.drop_index("ix_password_reset_tokens_id", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_user", table_name="password_reset_tokens")

    op.drop_constraint("uq_password_reset_token_hash", "password_reset_tokens", type_="unique")
    op.drop_table("password_reset_tokens")


# ── Seed data ──────────────────────────────────────────────────────

CONSENT_SEEDS = [
    ("PLATFORM_TERMS", "1.0.0", "Platform Terms of Service", "/legal/terms"),
    ("PRIVACY_POLICY", "1.0.0", "Privacy Policy", "/legal/privacy"),
    ("AGENT_TERMS", "1.0.0", "Agent Terms", "/legal/agent-terms"),
    ("VERIFICATION_TERMS", "1.0.0", "Verification Terms", "/legal/verification-terms"),
    ("REPORT_DISCLAIMER", "1.0.0", "Report Disclaimer", "/legal/report-disclaimer"),
]
CONSENT_EFFECTIVE_AT = datetime(2026, 1, 15, tzinfo=timezone.utc)


def _seed_audit_columns(now: datetime) -> dict:
    return {
        "date_created": now,
        "date_updated": None,
        "deleted": False,
        "version": 1,
    }


def _seed_consent_documents() -> None:
    table = sa.table(
        "consent_documents",
        sa.column("id", sa.String),
        sa.column("type", sa.String),
        sa.column("consent_version", sa.String),
        sa.column("effective_at", sa.DateTime(timezone=True)),
        sa.column("title", sa.String),
        sa.column("href", sa.String),
        sa.column("date_created", sa.TIMESTAMP(timezone=True)),
        sa.column("date_updated", sa.TIMESTAMP(timezone=True)),
        sa.column("deleted", sa.Boolean),
        sa.column("version", sa.Integer),
    )
    # The bulk_insert driver only uses column names, so duplicate names just
    # need value entries. We pass the row dicts directly with the right keys.
    now = datetime.now(timezone.utc)
    rows = []
    for doc_type, ver, title, href in CONSENT_SEEDS:
        row = {
            "id": str(uuid.uuid4()),
            "type": doc_type,
            "consent_version": ver,
            "effective_at": CONSENT_EFFECTIVE_AT,
            "title": title,
            "href": href,
            **_seed_audit_columns(now),
        }
        # `version` (audit) overwrites `version` (semver) — explicitly use raw SQL.
        rows.append(row)

    # Use raw insert to avoid the duplicate-column-name collision.
    conn = op.get_bind()
    for row in rows:
        conn.execute(
            sa.text(
                "INSERT INTO consent_documents "
                "(id, type, consent_version, effective_at, title, href, date_created, deleted, version) "
                "VALUES (:id, :type, :consent_version, :effective_at, :title, :href, :date_created, :deleted, :version)"
            ),
            {
                "id": row["id"],
                "type": row["type"],
                "consent_version": row["consent_version"],
                "effective_at": row["effective_at"],
                "title": row["title"],
                "href": row["href"],
                "date_created": row["date_created"],
                "deleted": row["deleted"],
                "version": row["version"],
            },
        )


def _seed_super_admin() -> None:
    """Seed the first Super Admin if `SUPER_ADMIN_PASSWORD` is set in env.
    Idempotent: skipped if a user with the canonical email already exists."""
    password = os.getenv("SUPER_ADMIN_PASSWORD")
    if not password:
        return

    email = os.getenv("SUPER_ADMIN_EMAIL", "admin@veriprops.ng")
    conn = op.get_bind()
    existing = conn.execute(
        sa.text("SELECT 1 FROM users WHERE email = :email LIMIT 1"),
        {"email": email},
    ).first()
    if existing:
        return

    pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
    password_hash = pwd_context.hash(password)
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
            "id": str(uuid.uuid4()),
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


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    return name in sa_inspect(bind).get_table_names()


def upgrade() -> None:
    if not _table_exists('users'):
        _create_users()
    if not _table_exists('key_values'):
        _create_tab_key_values()
    if not _table_exists('oauth_identities'):
        _create_oauth_identities()
    if not _table_exists('consent_documents'):
        _create_consent_documents()
    if not _table_exists('user_consents'):
        _create_user_consents()
    if not _table_exists('device_sessions'):
        _create_device_sessions()
    if not _table_exists('security_events'):
        _create_security_events()
    if not _table_exists('password_reset_tokens'):
        _create_password_reset_tokens()
    if not _table_exists("signup_drafts"):
        _create_signup_drafts()

    # Data seeds belong here, not in app-level seeders.
    if not _table_exists('consent_documents'):
        _seed_consent_documents()
    if not _table_exists('users'):
        _seed_super_admin()


def downgrade() -> None:
    if not _table_exists('key_values'):
        _drop_tab_key_values()
    if not _table_exists('password_reset_tokens'):
        _drop_password_reset_tokens()
    if not _table_exists('security_events'):
        _drop_security_events()
    if not _table_exists('device_sessions'):
        _drop_device_sessions()
    if not _table_exists('user_consents'):
        _drop_user_consents()
    if not _table_exists('consent_documents'):
        _drop_consent_documents()
    if not _table_exists('oauth_identities'):
        _drop_oauth_identities()
    if not _table_exists('users'):
        _drop_users()
    if _table_exists("signup_drafts"):
        _drop_signup_drafts()
