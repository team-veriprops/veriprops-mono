"""Migration 0009 gives each task the commission its agent accepted it at, additively.

It must chain after 0008, leave one head, add exactly the nullable column the ORM declares — a
task accepted before it ran has no lock and is paid the live rate — and drop only that column on
the way down.
"""
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

from alembic.config import Config
from alembic.script import ScriptDirectory

from main.app.domain.verification.task.models import VerificationTask

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_REVISION = "0009_task_commission_lock"
_MIGRATION = _BACKEND_ROOT / "main" / "alembic" / "versions" / f"{_REVISION}.py"


def _scripts() -> ScriptDirectory:
    config = Config()
    config.set_main_option("script_location", str(_BACKEND_ROOT / "main" / "alembic"))
    return ScriptDirectory.from_config(config)


def _recorded(step: str):
    spec = importlib.util.spec_from_file_location("migration_0009", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # One parent, so the order of the guard and the DDL can be read off its call list.
    recorder = MagicMock()
    module.op, module.AlembicUtils = recorder.op, recorder.utils
    getattr(module, step)()
    return recorder


def test_it_chains_after_the_signup_drafts_migration_and_is_the_only_head():
    scripts = _scripts()
    assert scripts.get_heads() == [_REVISION]
    assert scripts.get_revision(_REVISION).down_revision == "0008_drop_signup_drafts"


def test_the_model_declares_a_nullable_amount():
    column = VerificationTask.__table__.c.commission_minor
    assert column.nullable is True
    assert column.server_default is None


def test_the_upgrade_adds_the_column_and_backfills_nothing():
    op = _recorded("upgrade").op
    table, column = op.add_column.call_args.args
    assert (table, column.name, column.nullable) == ("verification_tasks", "commission_minor", True)
    assert not op.execute.called


def test_the_downgrade_drops_only_that_column():
    _recorded("downgrade").op.drop_column.assert_called_once_with("verification_tasks", "commission_minor")


def test_the_downgrade_refuses_while_an_unpaid_task_holds_a_locked_rate():
    """Dropping the column would pay such a task the live rate instead of the one its agent
    accepted; a task already approved or cancelled has been settled and loses nothing."""
    recorder = _recorded("downgrade")
    count_sql = recorder.utils.refuse_if_rows.call_args.args[0]
    assert "commission_minor IS NOT NULL" in count_sql
    assert "'APPROVED'" in count_sql and "'CANCELLED'" in count_sql
    names = [c[0] for c in recorder.mock_calls]
    assert names.index("utils.refuse_if_rows") < names.index("op.drop_column")
