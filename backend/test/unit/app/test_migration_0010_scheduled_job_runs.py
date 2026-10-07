"""Migration 0010 records when each scheduled job last ran, so any clock can tell what is due.

It must chain after 0009, create the table and the one unique index on `name`
that the model declares, and drop exactly those on the way down. The rows are bookkeeping, not
business data: a downgrade loses only "when did this sweep last run", and a later upgrade
re-anchors every job at its first sight, so no refusal guards it.
"""
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

from alembic.config import Config
from alembic.script import ScriptDirectory

from main.app.domain.scheduled_job.models import ScheduledJobRun

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_REVISION = "0010_scheduled_job_runs"
_MIGRATION = _BACKEND_ROOT / "main" / "alembic" / "versions" / f"{_REVISION}.py"
_INDEX = "ix_scheduled_job_runs_name"


def _scripts() -> ScriptDirectory:
    config = Config()
    config.set_main_option("script_location", str(_BACKEND_ROOT / "main" / "alembic"))
    return ScriptDirectory.from_config(config)


def _recorded(step: str):
    spec = importlib.util.spec_from_file_location("migration_0010", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    recorder = MagicMock()
    module.op = recorder.op
    getattr(module, step)()
    return recorder


def test_it_chains_after_the_task_commission_migration():
    assert _scripts().get_revision(_REVISION).down_revision == "0009_task_commission_lock"


def test_the_model_declares_a_unique_name_and_a_nullable_last_run():
    table = ScheduledJobRun.__table__
    assert table.name == "scheduled_job_runs"
    assert table.c.name.nullable is False
    assert table.c.last_run_at.nullable is True
    index = next(i for i in table.indexes if i.name == _INDEX)
    assert index.unique and [c.name for c in index.columns] == ["name"]


def test_the_upgrade_creates_the_table_and_its_unique_index():
    op = _recorded("upgrade").op
    assert op.create_table.call_args.args[0] == "scheduled_job_runs"
    op.create_index.assert_called_once_with(_INDEX, "scheduled_job_runs", ["name"], unique=True)


def test_the_downgrade_drops_only_what_the_upgrade_made():
    op = _recorded("downgrade").op
    op.drop_index.assert_called_once_with(_INDEX, table_name="scheduled_job_runs")
    op.drop_table.assert_called_once_with("scheduled_job_runs")
