"""Migration 0002's downgrade refuses to discard an admin-set commission.

Going down, 0002 deletes the fixed per-role amounts and re-seeds the old role × tier rates. A role
still at its seeded default loses nothing, since the seed puts it back; a role an admin changed
would lose that decision silently. So the downgrade counts the rules that differ from
``DEFAULT_ROLE_COMMISSION_NGN_KOBO`` and refuses, before the delete, while there are any.
"""
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

from main.app.domain.commission_rule.models import DEFAULT_ROLE_COMMISSION_NGN_KOBO

_MIGRATION = Path(__file__).resolve().parents[3] / "main" / "alembic" / "versions" / "0002_fixed_agent_commission.py"


def _recorded_downgrade() -> MagicMock:
    spec = importlib.util.spec_from_file_location("migration_0002", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # One parent, so the order of the guards and the DDL can be read off its call list.
    recorder = MagicMock()
    module.op, module.AlembicUtils = recorder.op, recorder.utils
    module.downgrade()
    return recorder


def _rule_guard_sql(recorder: MagicMock) -> str:
    return next(
        c.args[0] for c in recorder.utils.refuse_if_rows.call_args_list if "commission_rules" in c.args[0]
    )


def test_it_counts_live_rules_that_differ_from_the_seeded_amounts():
    sql = _rule_guard_sql(_recorded_downgrade())
    assert "deleted = false" in sql
    for role, amount in DEFAULT_ROLE_COMMISSION_NGN_KOBO.items():
        assert f"('{role.value}', {amount})" in sql


def test_the_guard_runs_before_the_rules_are_deleted():
    recorder = _recorded_downgrade()
    sql = _rule_guard_sql(recorder)
    names = [(c[0], c.args[0] if c.args else None) for c in recorder.mock_calls]
    guard_at = names.index(("utils.refuse_if_rows", sql))
    delete_at = names.index(("op.execute", "DELETE FROM commission_rules"))
    assert guard_at < delete_at
