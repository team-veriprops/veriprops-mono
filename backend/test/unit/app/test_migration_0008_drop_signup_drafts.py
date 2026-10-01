"""Migration 0008 drops the server-side signup drafts, purging the plaintext passwords they held.

It must chain after 0007, leave one head, and leave no model behind that still maps the table;
its downgrade recreates the table empty, so no draft row can come back.
"""
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

from alembic.config import Config
from alembic.script import ScriptDirectory

from main.app import core as _core, domain as _domain
from main.appodus_utils import BaseEntity

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_MIGRATION = _BACKEND_ROOT / "main" / "alembic" / "versions" / "0008_drop_signup_drafts.py"
_TABLE = "signup_drafts"


def _scripts() -> ScriptDirectory:
    config = Config()
    config.set_main_option("script_location", str(_BACKEND_ROOT / "main" / "alembic"))
    return ScriptDirectory.from_config(config)


def _recorded(step: str) -> MagicMock:
    spec = importlib.util.spec_from_file_location("migration_0008", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = MagicMock()
    getattr(module, step)()
    return module.op


def test_it_chains_after_the_refund_requests_migration_and_is_the_only_head():
    scripts = _scripts()
    assert scripts.get_heads() == ["0008_drop_signup_drafts"]
    assert scripts.get_revision("0008_drop_signup_drafts").down_revision == "0007_refund_requests"


def test_no_model_maps_the_dropped_table():
    _ = (_core, _domain)
    assert _TABLE not in BaseEntity.metadata.tables


def test_the_upgrade_drops_the_table_and_touches_nothing_else():
    op = _recorded("upgrade")
    op.drop_table.assert_called_once_with(_TABLE)
    assert not op.execute.called and not op.create_table.called


def test_the_downgrade_recreates_the_table_without_restoring_any_row():
    op = _recorded("downgrade")
    assert op.create_table.call_args.args[0] == _TABLE
    # An empty table: no bulk insert, no raw SQL that could put rows back.
    assert not op.bulk_insert.called and not op.execute.called
