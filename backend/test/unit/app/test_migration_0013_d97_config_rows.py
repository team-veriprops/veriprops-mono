"""Migration 0013 gives every database the two config rows D97 introduced.

`0001` seeds `system_config` from the live `CONFIG_DEFAULTS`, so a fresh build has a row for
`commission_min_margin_pct` and `remote_job_bonus_ngn_kobo`, while a database that ran an earlier
`0001` and then `0002` (D97) has neither. Readers fall back to the defaults, so nothing misbehaved,
but the two kinds of database differed. The upgrade inserts each row only where its key is absent,
so a fresh build and any admin edit are left alone. The downgrade removes nothing: it cannot tell
the rows this inserted from the ones `0001` seeded or an admin saved.
"""
import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock

from alembic.config import Config
from alembic.script import ScriptDirectory

from main.app.domain.system_config.models import CONFIG_DEFAULTS, ConfigKey

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_REVISION = "0013_d97_config_rows"
_MIGRATION = _BACKEND_ROOT / "main" / "alembic" / "versions" / f"{_REVISION}.py"


def _scripts() -> ScriptDirectory:
    config = Config()
    config.set_main_option("script_location", str(_BACKEND_ROOT / "main" / "alembic"))
    return ScriptDirectory.from_config(config)


def _module():
    spec = importlib.util.spec_from_file_location("migration_0013", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(step: str, present=()):
    """Run *step* against a connection whose `system_config` already holds the keys *present*."""
    module = _module()
    conn = MagicMock()

    def _execute(stmt, params=None):
        result = MagicMock()
        result.first.return_value = (1,) if params and params.get("key") in present else None
        return result

    conn.execute.side_effect = _execute
    module.op = MagicMock(get_bind=MagicMock(return_value=conn))
    getattr(module, step)()
    return module, conn


def _inserted(conn) -> list:
    return [c.args[1]["key"] for c in conn.execute.call_args_list
            if str(c.args[0]).startswith("INSERT INTO system_config")]


def test_it_chains_after_the_retries_migration_and_is_the_only_head():
    scripts = _scripts()
    assert scripts.get_heads() == [_REVISION]
    assert scripts.get_revision(_REVISION).down_revision == "0012_retries"


def test_its_rows_are_the_d97_keys_at_their_current_defaults():
    # Raw strings in the migration, by design; this pins them to the app's keys and defaults.
    rows = {row["key"]: json.loads(row["value_json"]) for row in _module().ROWS}
    assert rows == {
        ConfigKey.COMMISSION_MIN_MARGIN_PCT.value: CONFIG_DEFAULTS[ConfigKey.COMMISSION_MIN_MARGIN_PCT],
        ConfigKey.REMOTE_JOB_BONUS_NGN_KOBO.value: CONFIG_DEFAULTS[ConfigKey.REMOTE_JOB_BONUS_NGN_KOBO],
    }


def test_a_database_missing_both_rows_gets_both():
    module, conn = _run("upgrade")
    assert _inserted(conn) == [row["key"] for row in module.ROWS]


def test_a_key_already_present_is_left_alone():
    # A fresh build (seeded by 0001) or an admin's saved value.
    _, conn = _run("upgrade", present={"commission_min_margin_pct"})
    assert _inserted(conn) == ["remote_job_bonus_ngn_kobo"]
    _, conn = _run("upgrade", present={"commission_min_margin_pct", "remote_job_bonus_ngn_kobo"})
    assert _inserted(conn) == []


def test_the_downgrade_removes_nothing():
    _, conn = _run("downgrade")
    conn.execute.assert_not_called()
