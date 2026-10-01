"""schema_parity — the database's indexes and keys match what the models declare.

`alembic check` reported 142 differences between the ORM and a database migrated to head,
all from the squashed 0001 schema. None changes a column's data; together they leave the
schema a model reader cannot trust. This migration reconciles every one, so `alembic check`
reports none and CI can hold it there:

* **Redundant indexes dropped.** Every table carried a second unique index on `id`, which
  duplicates the primary key's own; and four tables indexed the `deleted` flag, which nearly
  every row shares, so the planner never uses it. `callbacks.handled` is the same case —
  it is only ever filtered alongside the indexed `external_id`.
* **Uniqueness moved from constraints to unique indexes.** Ten columns had a unique
  constraint *and* a separate plain index on the same column — two indexes doing one job.
  Each becomes a single unique index under the model's name. `ON CONFLICT (column)` targets
  either form, so inserts are unaffected.
* **Indexes renamed** to the models' `ix_<table>_<column>` names.
* **Missing indexes created** on lookup columns the models declare and queries use
  (`notifications.user_id`, `commissions.agent_id`, the `verification_id` columns, …).

Written in raw SQL with IF [NOT] EXISTS, decoupled from the app models like every migration,
so it applies cleanly to any database that ran 0001–0004.

Revision ID: 0005_schema_parity
Revises: 0004_payout_transfers
Create Date: 2026-09-28 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0005_schema_parity"
down_revision: Union[str, None] = "0004_payout_transfers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The id indexes 0001 named differently, and the one it made non-unique — restored as-is on
# downgrade.
_ODD_ID_INDEXES = {
    "conversation_participants": ("ix_conv_participants_id", True),
    "notification_preferences": ("ix_notif_prefs_id", True),
    "report_acknowledgements": ("ix_report_ack_id", True),
    "audit_logs": ("ix_audit_logs_id", False),
}
_DELETED_INDEXED = ("users", "messages", "audit_logs", "idempotency_keys")

# table, column, the unique constraint 0001 made, the plain index beside it (if any),
# and the unique index that replaces both.
_UNIQUE_SWAPS = [
    ("admin_invitations", "token_hash", "uq_admin_invitation_token_hash", "ix_admin_invitations_token_hash",
     "ix_admin_invitations_token_hash"),
    ("chargebacks", "gateway_event_id", "uq_chargebacks_gateway_event", None, "ix_chargebacks_gateway_event_id"),
    ("device_sessions", "refresh_token_hash", "uq_device_token_hash", None, "ix_device_sessions_refresh_token_hash"),
    ("password_reset_tokens", "token_hash", "uq_password_reset_token_hash", None,
     "ix_password_reset_tokens_token_hash"),
    ("payments", "tx_ref", "uq_payments_tx_ref", "ix_payments_tx_ref", "ix_payments_tx_ref"),
    ("referrals", "code", "uq_referrals_code", "ix_referrals_code", "ix_referrals_code"),
    ("referrals", "referrer_user_id", "uq_referrals_referrer", None, "ix_referrals_referrer_user_id"),
    ("users", "email_normalized", "uq_users_email", None, "ix_users_email_normalized"),
    ("verification_shares", "token", "uq_verification_shares_token", "ix_verification_shares_token",
     "ix_verification_shares_token"),
    ("verifications", "vid", "uq_verifications_vid", "ix_verifications_vid", "ix_verifications_vid"),
]

_RENAMES = [
    ("ix_agent_bank_accounts_agent", "ix_agent_bank_accounts_agent_id"),
    ("ix_chat_messages_task", "ix_chat_messages_task_id"),
    ("ix_disputes_agent", "ix_disputes_agent_id"),
    ("ix_payouts_agent", "ix_payouts_agent_id"),
    ("ix_recheck_requests_payment", "ix_recheck_requests_payment_id"),
    ("ix_referral_credits_verification", "ix_referral_credits_verification_id"),
    ("ix_upgrade_requests_payment", "ix_upgrade_requests_payment_id"),
]

# (index, table, column) the models declare and 0001 never built.
_NEW_INDEXES = [
    ("ix_admin_invitations_email_normalized", "admin_invitations", "email_normalized"),
    ("ix_admin_notes_verification_id", "admin_notes", "verification_id"),
    ("ix_chargebacks_payment_id", "chargebacks", "payment_id"),
    ("ix_chargebacks_verification_id", "chargebacks", "verification_id"),
    ("ix_chat_messages_conversation_id", "chat_messages", "conversation_id"),
    ("ix_commissions_agent_id", "commissions", "agent_id"),
    ("ix_commissions_task_id", "commissions", "task_id"),
    ("ix_commissions_verification_id", "commissions", "verification_id"),
    ("ix_conversation_participants_conversation_id", "conversation_participants", "conversation_id"),
    ("ix_conversation_participants_user_id", "conversation_participants", "user_id"),
    ("ix_conversations_verification_id", "conversations", "verification_id"),
    ("ix_data_erasure_requests_subject_user_id", "data_erasure_requests", "subject_user_id"),
    ("ix_disputes_customer_id", "disputes", "customer_id"),
    ("ix_disputes_verification_id", "disputes", "verification_id"),
    ("ix_notification_preferences_user_id", "notification_preferences", "user_id"),
    ("ix_notifications_user_id", "notifications", "user_id"),
    ("ix_oauth_user", "oauth_identities", "user_id"),
    ("ix_password_reset_tokens_user_id", "password_reset_tokens", "user_id"),
    ("ix_payments_gateway_event_id", "payments", "gateway_event_id"),
    ("ix_payments_verification", "payments", "verification_id"),
    ("ix_recheck_requests_customer_id", "recheck_requests", "customer_id"),
    ("ix_recheck_requests_verification_id", "recheck_requests", "verification_id"),
    ("ix_referral_credits_invitee_user_id", "referral_credits", "invitee_user_id"),
    ("ix_referral_credits_referrer_user_id", "referral_credits", "referrer_user_id"),
    ("ix_report_acknowledgements_customer_id", "report_acknowledgements", "customer_id"),
    ("ix_report_acknowledgements_verification_id", "report_acknowledgements", "verification_id"),
    ("ix_reports_verification_id", "reports", "verification_id"),
    ("ix_task_evidence_task_id", "task_evidence", "task_id"),
    ("ix_task_evidence_verification_id", "task_evidence", "verification_id"),
    ("ix_upgrade_requests_customer_id", "upgrade_requests", "customer_id"),
    ("ix_upgrade_requests_idempotency_key", "upgrade_requests", "idempotency_key"),
    ("ix_upgrade_requests_verification_id", "upgrade_requests", "verification_id"),
    ("ix_verification_shares_verification_id", "verification_shares", "verification_id"),
    ("ix_verification_tasks_assigned_agent_id", "verification_tasks", "assigned_agent_id"),
]

# Every plain index exactly on (id) that no constraint owns — never the primary key's own.
_REDUNDANT_ID_INDEXES = r"""
DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT i.indexname FROM pg_indexes i
    WHERE i.schemaname = 'public' AND i.indexdef ~ '\(id\)$'
      AND NOT EXISTS (SELECT 1 FROM pg_constraint c WHERE c.conname = i.indexname)
  LOOP
    EXECUTE format('DROP INDEX IF EXISTS public.%I', r.indexname);
  END LOOP;
END $$;
"""

# The standard ix_<table>_id restored on every table that has an id column (downgrade).
_RESTORE_ID_INDEXES = r"""
DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT c.table_name FROM information_schema.columns c
    JOIN information_schema.tables t ON t.table_name = c.table_name AND t.table_schema = c.table_schema
    WHERE c.table_schema = 'public' AND c.column_name = 'id' AND t.table_type = 'BASE TABLE'
      AND c.table_name NOT IN ({odd})
  LOOP
    EXECUTE format('CREATE UNIQUE INDEX IF NOT EXISTS %I ON public.%I (id)', 'ix_' || r.table_name || '_id', r.table_name);
  END LOOP;
END $$;
"""


def upgrade() -> None:
    op.execute(_REDUNDANT_ID_INDEXES)
    for table in _DELETED_INDEXED:
        op.execute(f"DROP INDEX IF EXISTS ix_{table}_deleted")
    op.execute("DROP INDEX IF EXISTS ix_callbacks_handled")

    for table, column, constraint, plain_index, unique_index in _UNIQUE_SWAPS:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {constraint}")
        if plain_index:
            op.execute(f"DROP INDEX IF EXISTS {plain_index}")
        op.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS {unique_index} ON {table} ({column})")

    for old, new in _RENAMES:
        op.execute(f"ALTER INDEX IF EXISTS {old} RENAME TO {new}")

    for index, table, column in _NEW_INDEXES:
        op.execute(f"CREATE INDEX IF NOT EXISTS {index} ON {table} ({column})")


def downgrade() -> None:
    for index, _table, _column in _NEW_INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {index}")

    for old, new in _RENAMES:
        op.execute(f"ALTER INDEX IF EXISTS {new} RENAME TO {old}")

    for table, column, constraint, plain_index, unique_index in _UNIQUE_SWAPS:
        op.execute(f"DROP INDEX IF EXISTS {unique_index}")
        op.execute(f"ALTER TABLE {table} ADD CONSTRAINT {constraint} UNIQUE ({column})")
        if plain_index:
            op.execute(f"CREATE INDEX IF NOT EXISTS {plain_index} ON {table} ({column})")

    op.execute("CREATE INDEX IF NOT EXISTS ix_callbacks_handled ON callbacks (handled)")
    for table in _DELETED_INDEXED:
        op.execute(f"CREATE INDEX IF NOT EXISTS ix_{table}_deleted ON {table} (deleted)")

    odd = ", ".join(f"'{t}'" for t in _ODD_ID_INDEXES)
    op.execute(_RESTORE_ID_INDEXES.format(odd=odd))
    for table, (index, unique) in _ODD_ID_INDEXES.items():
        op.execute(f"CREATE {'UNIQUE ' if unique else ''}INDEX IF NOT EXISTS {index} ON {table} (id)")
