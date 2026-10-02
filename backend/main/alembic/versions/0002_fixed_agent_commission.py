"""fixed_agent_commission — an agent's commission is a fixed amount per role (D97).

The commission used to be a share of the tier price, configured per role × tier in basis points
(D30). That paid the same work differently by tier (a REGISTRY task earned ₦20,000 on BASIC and
₦36,000 on PREMIUM) and less on a referral-discounted case, which steered agents towards the
expensive jobs. ``commission_rules`` is re-keyed by role alone, and each row now holds a fixed
NGN-kobo amount, seeded from ``DEFAULT_ROLE_COMMISSION_NGN_KOBO``.

**The role × tier rows are replaced outright, with no ``refuse_if_rows`` guard.** This is a
deliberate, owner-approved exception to the refuse-on-data-loss rule: those rows are superseded
pricing configuration, not business records, and they cannot be translated, because a percentage
of three different prices has no single fixed-amount equivalent. Nothing is lost all the same:
before the delete, every rate is written to ``audit_logs`` (``ADMIN_CONFIG_CHANGED`` on
``commission_rule``) with the default it was seeded at and whether an admin had changed it, so an
edited rate can be read back and re-entered as an amount. The commissions those rates produced are
stored as amounts on ``commissions`` and are not touched. The downgrade has no such exception: it
refuses while any fixed amount differs from its seeded default.

``commissions`` also gains ``kind`` (``BASE`` / ``REMOTE_BONUS``): the remote bonus an aging pool
task carries is paid as its own ledger line beside the task's fixed commission, so earnings can
show it apart. Existing rows are all fixed commissions and take ``BASE``.

Revision ID: 0002_fixed_agent_commission
Revises: 0019_sla_breach_marker
Create Date: 2026-09-27 00:00:00.000000
"""
from typing import Any, Mapping, Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.alembic.utils import AlembicUtils
from main.app.domain.commission_rule.models import DEFAULT_ROLE_COMMISSION_NGN_KOBO
from main.app.domain.verification.scoring.models import DEFAULT_TRUST_WEIGHTS
from main.appodus_utils import Utils
from main.appodus_utils.db.models import JSONB_VARIANT

revision: str = "0002_fixed_agent_commission"
down_revision: Union[str, None] = "0019_sla_breach_marker"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "commission_rules"
_LIVE = "deleted = false"
_ROLE_GUARD = "uq_commission_rule_role"
_ROLE_TIER_GUARD = "uq_commission_rule_role_tier"
_COMMISSIONS = "commissions"

# Raw strings by design — migrations stay decoupled from app enums.
_AUDIT_ACTION = "ADMIN_CONFIG_CHANGED"
_AUDIT_RESOURCE = "commission_rule"
_KIND_BASE = "BASE"

# The D30 model, for downgrade only: basis points per whole percent and the agents' share of
# the tier price (the setting that carried it is gone).
_BPS_PER_PERCENT = 100
_AGENT_COMMISSION_SHARE = 0.40


def _commission_rule_rows() -> list[dict]:
    """One fixed commission per role, in NGN kobo (§20.1 / D97)."""
    return [
        {"role": role.value, "amount_ngn_kobo": amount}
        for role, amount in DEFAULT_ROLE_COMMISSION_NGN_KOBO.items()
    ]


def _legacy_rate_rows() -> list[dict]:
    """The D30 per-(role, tier) basis-point rates, rebuilt for downgrade."""
    return [
        {
            "role": role.value,
            "tier": tier.value,
            "rate_bps": round(weight * _BPS_PER_PERCENT * _AGENT_COMMISSION_SHARE),
        }
        for tier, role_weights in DEFAULT_TRUST_WEIGHTS.items()
        for role, weight in role_weights.items()
    ]


def _snapshot_rows(stored: list[Mapping[str, Any]]) -> list[dict]:
    """One audit row per replaced role × tier rate: its value, the default it was seeded at, and
    whether an admin had changed it."""
    defaults = {(r["role"], r["tier"]): r["rate_bps"] for r in _legacy_rate_rows()}
    rows = []
    for rule in stored:
        default = defaults.get((rule["role"], rule["tier"]))
        rows.append({
            "action": _AUDIT_ACTION,
            "resource_type": _AUDIT_RESOURCE,
            "resource_id": str(rule["id"]),
            "actor_id": None,
            "details": {
                "role": rule["role"],
                "tier": rule["tier"],
                "rate_bps": rule["rate_bps"],
                "default_rate_bps": default,
                "customised": rule["rate_bps"] != default,
                "superseded_by": revision,
            },
        })
    return rows


def _snapshot_replaced_rates() -> None:
    """Keep every rate this revision replaces, in the audit log, before it is deleted."""
    conn = op.get_bind()
    stored = conn.execute(sa.text(
        f"SELECT id, role, tier, rate_bps FROM {_TABLE} WHERE deleted = false"
    )).mappings().all()
    insert = sa.text(
        "INSERT INTO audit_logs (id, actor_id, action, resource_type, resource_id, details, "
        "occurred_at, date_created, deleted, version) "
        "VALUES (:id, :actor_id, :action, :resource_type, :resource_id, :details, :now, :now, FALSE, 1)"
    ).bindparams(sa.bindparam("details", type_=JSONB_VARIANT))
    for row in _snapshot_rows(list(stored)):
        conn.execute(insert, {"id": Utils.generate_uuid(), "now": Utils.datetime_now(), **row})


def _add_commission_kind() -> None:
    op.add_column(
        _COMMISSIONS,
        sa.Column("kind", sa.String(length=16), nullable=False, server_default=_KIND_BASE),
    )


def _drop_commission_kind() -> None:
    # A bonus line dropped to the old single-kind ledger would read as a second fixed
    # commission for its task, so a downgrade with bonuses paid refuses rather than lose them.
    AlembicUtils.refuse_if_rows(
        f"SELECT count(*) FROM {_COMMISSIONS} WHERE kind <> '{_KIND_BASE}'",
        "remote-bonus commission lines have no place in the pre-0002 ledger",
    )
    op.drop_column(_COMMISSIONS, "kind")


def _clear_rules() -> None:
    # Superseded configuration, replaced outright by owner decision (see the module docstring).
    op.execute(f"DELETE FROM {_TABLE}")


def _refuse_customised_amounts() -> None:
    # Going down, the exception above does not apply: a role still at its seeded amount loses
    # nothing (the seed would put it back), but an amount an admin set has no D30 equivalent and
    # would vanish. Refuse while any live rule differs from its default.
    defaults = ", ".join(f"('{row['role']}', {row['amount_ngn_kobo']})" for row in _commission_rule_rows())
    AlembicUtils.refuse_if_rows(
        f"SELECT count(*) FROM {_TABLE} WHERE deleted = false "
        f"AND (role, amount_ngn_kobo) NOT IN ({defaults})",
        "admin-set fixed commissions have no equivalent in the pre-0002 role x tier rates",
    )


def _rekey_by_role() -> None:
    op.drop_index(_ROLE_TIER_GUARD, table_name=_TABLE)
    op.drop_column(_TABLE, "rate_bps")
    op.drop_column(_TABLE, "tier")
    op.add_column(
        _TABLE, sa.Column("amount_ngn_kobo", sa.BigInteger(), nullable=False, server_default="0")
    )
    op.create_index(_ROLE_GUARD, _TABLE, ["role"], unique=True, postgresql_where=sa.text(_LIVE))


def _rekey_by_role_and_tier() -> None:
    op.drop_index(_ROLE_GUARD, table_name=_TABLE)
    op.drop_column(_TABLE, "amount_ngn_kobo")
    op.add_column(_TABLE, sa.Column("tier", sa.String(length=16), nullable=False))
    op.add_column(_TABLE, sa.Column("rate_bps", sa.Integer(), nullable=False, server_default="0"))
    op.create_index(
        _ROLE_TIER_GUARD, _TABLE, ["role", "tier"], unique=True, postgresql_where=sa.text(_LIVE)
    )


def _insert_rows(columns: list[str], rows: list[dict]) -> None:
    conn = op.get_bind()
    names = ", ".join(columns)
    params = ", ".join(f":{c}" for c in columns)
    for row in rows:
        conn.execute(
            sa.text(
                f"INSERT INTO {_TABLE} (id, {names}, date_created, deleted, version) "
                f"VALUES (:id, {params}, :now, FALSE, 1)"
            ),
            {"id": Utils.generate_uuid(), "now": Utils.datetime_now(), **row},
        )


def upgrade() -> None:
    _snapshot_replaced_rates()
    _clear_rules()
    _rekey_by_role()
    _insert_rows(["role", "amount_ngn_kobo"], _commission_rule_rows())
    _add_commission_kind()


def downgrade() -> None:
    _refuse_customised_amounts()
    _drop_commission_kind()
    _clear_rules()
    _rekey_by_role_and_tier()
    _insert_rows(["role", "tier", "rate_bps"], _legacy_rate_rows())
