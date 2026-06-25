"""auto_generated

Revision ID: fdd959a2cfda
Revises: 
Create Date: 2025-06-01 02:19:26.646342

"""
import json
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import JSON
from sqlalchemy.ext.mutable import MutableList

from main.alembic.utils import AlembicUtils
from main.app.config.settings import settings
from main.appodus_utils import Utils
from main.appodus_utils.db.models import UTCDateTime, JSONB_VARIANT

# revision identifiers, used by Alembic.
revision: str = 'fdd959a2cfda'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── helpers ────────────────────────────────────────────────────────


def _create_tab_key_values():
    op.create_table('key_values', sa.Column('key', sa.String(length=128), nullable=False),
                    sa.Column('value', sa.LargeBinary(), nullable=False),
                    sa.Column('expires_at', UTCDateTime, nullable=False),
                    sa.PrimaryKeyConstraint('key'))
    op.create_index(op.f('ix_key_values_key'), 'key_values', ['key'], unique=True)


def _drop_tab_key_values():
    op.drop_index(op.f('ix_key_values_key'), table_name='key_values')
    op.drop_table('key_values')


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
        sa.Column("locked_until", UTCDateTime, nullable=True),
        sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"),
        *AlembicUtils.base_audit_columns(),
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
        *AlembicUtils.base_audit_columns(),
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
        sa.Column("effective_at", UTCDateTime, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("href", sa.String(length=255), nullable=False),
        *AlembicUtils.base_audit_columns(),
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
        sa.Column("accepted_at", UTCDateTime, nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("device_fingerprint", sa.String(length=128), nullable=True),
        *AlembicUtils.base_audit_columns(),
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
        sa.Column("last_active_at", UTCDateTime, nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.Column("revoked_at", UTCDateTime, nullable=True),
        *AlembicUtils.base_audit_columns(),
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
        sa.Column("occurred_at", UTCDateTime, nullable=False),
        *AlembicUtils.base_audit_columns(),
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
        sa.Column("expires_at", UTCDateTime, nullable=False),
        sa.Column("consumed_at", UTCDateTime, nullable=True),
        *AlembicUtils.base_audit_columns(),
        sa.UniqueConstraint("token_hash", name="uq_password_reset_token_hash"),
    )
    op.create_index("ix_password_reset_user", "password_reset_tokens", ["user_id"], unique=False)
    op.create_index("ix_password_reset_tokens_id", "password_reset_tokens", ["id"], unique=True)


def _drop_password_reset_tokens():
    op.drop_index("ix_password_reset_tokens_id", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_user", table_name="password_reset_tokens")

    op.drop_constraint("uq_password_reset_token_hash", "password_reset_tokens", type_="unique")
    op.drop_table("password_reset_tokens")


def _create_messages():
    op.create_table('messages',
                    sa.Column('channel', sa.String(length=20), nullable=False),
                    sa.Column('to', JSONB_VARIANT,
                              nullable=False),
                    sa.Column('payload', JSONB_VARIANT,
                              nullable=False),
                    sa.Column('status', sa.String(length=20), nullable=False),
                    sa.Column('provider', sa.String(length=50), nullable=True),
                    sa.Column('provider_id', sa.String(length=255), nullable=True),
                    sa.Column('error', sa.Text(), nullable=True),
                    sa.Column('retry_count', sa.Integer(), nullable=True),
                    sa.Column('priority', sa.Integer(), nullable=True),
                    sa.Column('scheduled_at', UTCDateTime, nullable=True),
                    sa.Column('sent_at', UTCDateTime, nullable=True),
                    sa.Column('delivered_at', UTCDateTime, nullable=True),
                    sa.Column('extras', JSONB_VARIANT,
                              nullable=True),
                    sa.Column('callback_url', sa.String(length=100), nullable=True),
                    *AlembicUtils.base_audit_columns(),
                    )
    op.create_index(op.f('ix_messages_deleted'), 'messages', ['deleted'], unique=False)
    op.create_index(op.f('ix_messages_id'), 'messages', ['id'], unique=True)

def _drop_messages():
    op.drop_index(op.f('ix_messages_id'), table_name='messages')
    op.drop_index(op.f('ix_messages_deleted'), table_name='messages')
    op.drop_table('messages')

# ── Seed data ──────────────────────────────────────────────────────

CONSENT_SEEDS = [
    ("PLATFORM_TERMS", "1.0.0", "Platform Terms of Service", "/legal/terms"),
    ("PRIVACY_POLICY", "1.0.0", "Privacy Policy", "/legal/privacy"),
    ("AGENT_TERMS", "1.0.0", "Agent Terms", "/legal/agent-terms"),
    ("VERIFICATION_TERMS", "1.0.0", "Verification Terms", "/legal/verification-terms"),
    ("REPORT_DISCLAIMER", "1.0.0", "Report Disclaimer", "/legal/report-disclaimer"),
]
CONSENT_EFFECTIVE_AT = Utils.datetime_now()


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
    
def _seed_super_admin() -> None:
    """Seed the first Super Admin if `SUPER_ADMIN_PASSWORD` is set in env.
    Idempotent: skipped if a user with the canonical email already exists."""
    password = settings.SUPER_ADMIN_PASSWORD  # os.getenv("SUPER_ADMIN_PASSWORD")
    email = settings.SUPER_ADMIN_EMAIL  # os.getenv("SUPER_ADMIN_EMAIL")
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


def upgrade() -> None:
    if not AlembicUtils.table_exists('users'):
        _create_users()
    if not AlembicUtils.table_exists('key_values'):
        _create_tab_key_values()
    if not AlembicUtils.table_exists('oauth_identities'):
        _create_oauth_identities()
    if not AlembicUtils.table_exists('consent_documents'):
        _create_consent_documents()
    if not AlembicUtils.table_exists('user_consents'):
        _create_user_consents()
    if not AlembicUtils.table_exists('device_sessions'):
        _create_device_sessions()
    if not AlembicUtils.table_exists('security_events'):
        _create_security_events()
    if not AlembicUtils.table_exists('password_reset_tokens'):
        _create_password_reset_tokens()
    if not AlembicUtils.table_exists("signup_drafts"):
        _create_signup_drafts()
    if not AlembicUtils.table_exists("messages"):
        _create_messages()

    # Data seeds belong here, not in app-level seeders.
    if AlembicUtils.table_exists('consent_documents'):
        _seed_consent_documents()
    if AlembicUtils.table_exists('users'):
        _seed_super_admin()


def downgrade() -> None:
    if not AlembicUtils.table_exists('key_values'):
        _drop_tab_key_values()
    if not AlembicUtils.table_exists('password_reset_tokens'):
        _drop_password_reset_tokens()
    if not AlembicUtils.table_exists('security_events'):
        _drop_security_events()
    if not AlembicUtils.table_exists('device_sessions'):
        _drop_device_sessions()
    if not AlembicUtils.table_exists('user_consents'):
        _drop_user_consents()
    if not AlembicUtils.table_exists('consent_documents'):
        _drop_consent_documents()
    if not AlembicUtils.table_exists('oauth_identities'):
        _drop_oauth_identities()
    if not AlembicUtils.table_exists('users'):
        _drop_users()
    if AlembicUtils.table_exists("signup_drafts"):
        _drop_signup_drafts()
    if AlembicUtils.table_exists("messages"):
        _drop_messages()
