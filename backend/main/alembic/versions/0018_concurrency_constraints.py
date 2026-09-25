"""concurrency_constraints — uniqueness that ignores soft-deleted rows, and the guards that were missing.

Three changes, all to the unique guards the services lean on under concurrent requests:

* **Narrowed.** Services look rows up among live rows (`deleted = false`), but these unique
  constraints covered every row. So a soft delete (a discarded signup draft, an unlinked OAuth
  identity, a replaced WhatsApp link, a retired config row) blocked re-creating it for good,
  and the insert failed as a 500. Each constraint becomes a partial unique index under the
  same name. An upgrade's idempotency key is unique only among **pending** upgrades: a
  cancelled one must not block its retry. Idempotency keys become unique per scope.
* **Added.** Where the code already assumed a single live row (`scalar_one_or_none`,
  `.first()`) but nothing enforced it, concurrent requests produced silent duplicates:
  double referral credits, two agent profiles, split conversation threads, repeated report
  numbers, two accounts on one phone number. Each gets a partial unique index.
* **Backfill.** OAuth signups store the placeholder phone `0000000000`, and its derived
  `phone_e164` (`+2340000000000`) was shared by every OAuth user. It is not a number anyone
  owns, so it becomes NULL before the phone guard is added.

Adding a guard over existing duplicates is refused, not repaired. The pre-check lists them and
aborts, and nothing is deleted, because which duplicate is the right one is a data decision.
Offline (`--sql`) runs skip the pre-check, which needs a database to read.

Downgrade restores the full-table constraints. It fails if soft-deleted rows now duplicate
live ones, which is exactly what this migration allows. The phone backfill is not reversed:
the placeholder was never a real number.

Revision ID: 0018_concurrency_constraints
Revises: 0017_session_pkey_name
Create Date: 2026-09-24 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op

revision: str = "0018_concurrency_constraints"
down_revision: Union[str, None] = "0017_session_pkey_name"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Raw strings by design — migrations stay decoupled from app enums and constants.
_LIVE = "deleted = false"
_OAUTH_PLACEHOLDER_PHONE = "0000000000"

# (table, name, columns, predicate): full-table unique constraints narrowed to a partial index.
NARROWED = [
    ("signup_drafts", "uq_signup_drafts_email", ["email"], _LIVE),
    ("oauth_identities", "uq_oauth_provider_subject", ["provider", "subject"], _LIVE),
    ("whatsapp_links", "uq_whatsapp_links_user_id", ["user_id"], _LIVE),
    ("whatsapp_links", "uq_whatsapp_links_phone_e164", ["phone_e164"], _LIVE),
    ("upgrade_requests", "uq_upgrade_requests_key", ["idempotency_key"], f"{_LIVE} AND status = 'PENDING'"),
    ("system_config", "uq_system_config_key", ["key"], _LIVE),
    ("pricing_tier_config", "uq_pricing_tier_config_tier", ["tier"], _LIVE),
    ("commission_rules", "uq_commission_rule_role_tier", ["role", "tier"], _LIVE),
    ("trust_score_weight_config", "uq_trust_weight_tier_role", ["tier", "role"], _LIVE),
]

# Idempotency keys: unique on `key` alone becomes unique per scope, over live rows.
_IDEMPOTENCY_TABLE = "idempotency_keys"
_IDEMPOTENCY_OLD = ("uq_idempotency_key", ["key"])
IDEMPOTENCY = (_IDEMPOTENCY_TABLE, "uq_idempotency_scope_key", ["scope", "key"], _LIVE)

# (table, name, columns, predicate): guards the code assumed but nothing enforced.
ADDED = [
    ("agent_profiles", "uq_agent_profiles_user_id", ["user_id"], _LIVE),
    ("referral_credits", "uq_referral_credits_invitee", ["invitee_user_id"], _LIVE),
    ("notification_preferences", "uq_notif_prefs_user_event", ["user_id", "event_type"], _LIVE),
    ("reports", "uq_reports_verification_version", ["verification_id", "report_version"], _LIVE),
    (
        "conversations", "uq_conversations_verification_type", ["verification_id", "type"],
        f"{_LIVE} AND verification_id IS NOT NULL",
    ),
    (
        "conversations", "uq_conversations_web_support_owner", ["created_by"],
        f"{_LIVE} AND type = 'GENERAL_SUPPORT' AND channel = 'WEB'",
    ),
    (
        "conversations", "uq_conversations_whatsapp_number", ["external_ref"],
        f"{_LIVE} AND channel = 'WHATSAPP'",
    ),
    ("whatsapp_number_health", "uq_whatsapp_number_health_phone_number_id", ["phone_number_id"], _LIVE),
    ("users", "uq_users_phone_e164", ["phone_e164"], f"{_LIVE} AND phone_e164 IS NOT NULL"),
]

# How many duplicate keys the pre-check names per guard before summarising.
_SHOWN_PER_GUARD = 5


def assert_no_duplicates(bind) -> None:
    """Refuse to add a guard the data already violates; list the violations. Never deletes."""
    problems = []
    for table, name, columns, predicate in ADDED:
        cols = ", ".join(columns)
        rows = bind.execute(sa.text(
            f"SELECT {cols}, count(*) FROM {table} WHERE {predicate} "
            f"GROUP BY {cols} HAVING count(*) > 1 ORDER BY count(*) DESC"
        )).fetchall()
        if rows:
            shown = "; ".join(
                f"({', '.join(str(v) for v in row[:-1])}) x{row[-1]}" for row in rows[:_SHOWN_PER_GUARD]
            )
            more = f" and {len(rows) - _SHOWN_PER_GUARD} more" if len(rows) > _SHOWN_PER_GUARD else ""
            problems.append(f"{name} on {table}({cols}): {shown}{more}")
    if problems:
        raise RuntimeError(
            "Cannot add unique guards over existing duplicates. Resolve these rows (keep one "
            "live row per key, soft-delete the rest), then re-run the migration:\n  "
            + "\n  ".join(problems)
        )


def _partial_unique_index(table: str, name: str, columns: list, predicate: str) -> None:
    op.create_index(name, table, columns, unique=True, postgresql_where=sa.text(predicate))


def upgrade() -> None:
    op.execute(
        f"UPDATE users SET phone_e164 = NULL WHERE phone = '{_OAUTH_PLACEHOLDER_PHONE}'"
    )
    if not context.is_offline_mode():
        assert_no_duplicates(op.get_bind())

    for table, name, columns, predicate in NARROWED:
        op.drop_constraint(name, table, type_="unique")
        _partial_unique_index(table, name, columns, predicate)

    old_name, _ = _IDEMPOTENCY_OLD
    op.drop_constraint(old_name, _IDEMPOTENCY_TABLE, type_="unique")
    _partial_unique_index(*IDEMPOTENCY)

    for table, name, columns, predicate in ADDED:
        _partial_unique_index(table, name, columns, predicate)


def downgrade() -> None:
    for table, name, _columns, _predicate in reversed(ADDED):
        op.drop_index(name, table_name=table)

    table, name, _columns, _predicate = IDEMPOTENCY
    op.drop_index(name, table_name=table)
    old_name, old_columns = _IDEMPOTENCY_OLD
    op.create_unique_constraint(old_name, _IDEMPOTENCY_TABLE, old_columns)

    for table, name, columns, _predicate in reversed(NARROWED):
        op.drop_index(name, table_name=table)
        op.create_unique_constraint(name, table, columns)
