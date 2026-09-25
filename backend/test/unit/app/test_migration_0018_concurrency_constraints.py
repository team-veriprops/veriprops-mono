"""Migration 0018: uniqueness that ignores soft-deleted rows, plus the guards that were missing.

Three things are pinned here, with no database:
- the SQL the migration emits, compiled offline, both ways;
- that every model declares the same partial unique indexes as the migration, since
  `insert_or_get` targets them by columns and predicate;
- that the duplicate pre-check refuses to add a guard over existing duplicates and names them,
  rather than deleting data.
"""
import importlib.util
import io
import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from alembic import command
from alembic.config import Config

from main.app import core as _core, domain as _domain
from main.appodus_utils import BaseEntity

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_MIGRATION = _BACKEND_ROOT / "main" / "alembic" / "versions" / "0018_concurrency_constraints.py"
_FROM, _TO = "0017_session_pkey_name", "0018_concurrency_constraints"


def _migration():
    spec = importlib.util.spec_from_file_location("migration_0018", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _offline_sql(direction: str) -> str:
    buffer = io.StringIO()
    cfg = Config(str(_BACKEND_ROOT / "alembic.ini"), output_buffer=buffer)
    cfg.set_main_option("script_location", str(_BACKEND_ROOT / "main" / "alembic"))
    if direction == "upgrade":
        command.upgrade(cfg, f"{_FROM}:{_TO}", sql=True)
    else:
        command.downgrade(cfg, f"{_TO}:{_FROM}", sql=True)
    return " ".join(buffer.getvalue().split())


def _norm(sql: str) -> str:
    return re.sub(r"\s+", " ", sql.replace("(", " ( ").replace(")", " ) ")).strip().lower()


@pytest.fixture(scope="module")
def upgrade_sql() -> str:
    return _offline_sql("upgrade")


@pytest.fixture(scope="module")
def downgrade_sql() -> str:
    return _offline_sql("downgrade")


def test_it_follows_the_squashed_head():
    module = _migration()
    assert (module.revision, module.down_revision) == (_TO, _FROM)


def test_oauth_placeholder_phones_stop_posing_as_a_real_number_first(upgrade_sql):
    backfill = "UPDATE users SET phone_e164 = NULL WHERE phone = '0000000000'"
    assert backfill in upgrade_sql
    # The backfill has to precede the guard, or every OAuth signup would collide on it.
    assert upgrade_sql.index(backfill) < upgrade_sql.index("CREATE UNIQUE INDEX uq_users_phone_e164")


@pytest.mark.parametrize("table, name, columns, where", _migration().NARROWED)
def test_a_narrowed_guard_swaps_the_constraint_for_a_partial_index(upgrade_sql, downgrade_sql, table, name, columns, where):
    assert f"ALTER TABLE {table} DROP CONSTRAINT {name}" in upgrade_sql
    assert f"CREATE UNIQUE INDEX {name} ON {table} ({', '.join(columns)}) WHERE {where}" in upgrade_sql
    assert f"DROP INDEX {name}" in downgrade_sql
    assert f"ALTER TABLE {table} ADD CONSTRAINT {name} UNIQUE ({', '.join(columns)})" in downgrade_sql


@pytest.mark.parametrize("table, name, columns, where", _migration().ADDED)
def test_an_added_guard_is_a_partial_unique_index(upgrade_sql, downgrade_sql, table, name, columns, where):
    assert f"CREATE UNIQUE INDEX {name} ON {table} ({', '.join(columns)}) WHERE {where}" in upgrade_sql
    assert f"DROP INDEX {name}" in downgrade_sql


def test_idempotency_keys_are_unique_per_scope(upgrade_sql, downgrade_sql):
    assert "ALTER TABLE idempotency_keys DROP CONSTRAINT uq_idempotency_key" in upgrade_sql
    assert (
        "CREATE UNIQUE INDEX uq_idempotency_scope_key ON idempotency_keys (scope, key) WHERE deleted = false"
        in upgrade_sql
    )
    assert "ALTER TABLE idempotency_keys ADD CONSTRAINT uq_idempotency_key UNIQUE (key)" in downgrade_sql


@pytest.mark.parametrize("table, name, columns, where", [*_migration().NARROWED, *_migration().ADDED, _migration().IDEMPOTENCY])
def test_the_model_declares_the_same_partial_index(table, name, columns, where):
    _ = (_core, _domain)
    model_table = BaseEntity.metadata.tables[table]
    [index] = [i for i in model_table.indexes if i.name == name]
    assert index.unique
    assert [c.name for c in index.columns] == columns
    assert _norm(str(index.dialect_options["postgresql"]["where"])) == _norm(where)
    # No leftover full-table unique constraint of the same name.
    assert name not in {c.name for c in model_table.constraints}


def test_the_pre_check_names_duplicates_instead_of_deleting_them():
    module = _migration()
    bind = MagicMock()

    def _execute(stmt):
        result = MagicMock()
        sql = str(stmt)
        result.fetchall.return_value = [("u-1", 2)] if "FROM agent_profiles" in sql else []
        return result

    bind.execute.side_effect = _execute

    with pytest.raises(RuntimeError) as refused:
        module.assert_no_duplicates(bind)

    message = str(refused.value)
    assert "uq_agent_profiles_user_id" in message and "u-1" in message
    issued = [str(c.args[0]).upper() for c in bind.execute.call_args_list]
    assert all(sql.startswith("SELECT") for sql in issued)
    assert not any("DELETE FROM" in sql or "UPDATE " in sql for sql in issued)


def test_the_pre_check_passes_a_clean_database():
    module = _migration()
    bind = MagicMock()
    bind.execute.return_value.fetchall.return_value = []

    module.assert_no_duplicates(bind)  # no raise
