"""Migration 0012 lets a failed sweep and a failing broadcast page be retried, boundedly.

* `scheduled_job_runs.retry_at` — when a job that raised is due again (sooner than its next
  normal run). Nullable: no row is waiting on a retry when this runs.
* `broadcasts.fanout_failures` — consecutive failed attempts at the current fan-out page; at the
  cap the broadcast becomes FAILED. Defaults to 0.

The downgrade drops both, refusing while a broadcast is FAILED: the code it returns to has no
such status, and would fail to read that broadcast at all.
"""
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

from alembic.config import Config
from alembic.script import ScriptDirectory

from main.app.domain.broadcast.models import Broadcast
from main.app.domain.scheduled_job.models import ScheduledJobRun

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_REVISION = "0012_retries"
_MIGRATION = _BACKEND_ROOT / "main" / "alembic" / "versions" / f"{_REVISION}.py"


def _scripts() -> ScriptDirectory:
    config = Config()
    config.set_main_option("script_location", str(_BACKEND_ROOT / "main" / "alembic"))
    return ScriptDirectory.from_config(config)


def _recorded(step: str):
    spec = importlib.util.spec_from_file_location("migration_0012", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    recorder = MagicMock()
    module.op, module.AlembicUtils = recorder.op, recorder.utils
    getattr(module, step)()
    return recorder


def test_it_chains_after_the_broadcast_fanout_migration_and_is_the_only_head():
    scripts = _scripts()
    assert scripts.get_heads() == [_REVISION]
    assert scripts.get_revision(_REVISION).down_revision == "0011_broadcast_fanout"


def test_the_models_declare_both_columns():
    assert ScheduledJobRun.__table__.c.retry_at.nullable is True
    failures = Broadcast.__table__.c.fanout_failures
    assert failures.nullable is False and str(failures.server_default.arg) == "0"


def test_the_upgrade_adds_exactly_those_columns():
    added = {(c.args[0], c.args[1].name) for c in _recorded("upgrade").op.add_column.call_args_list}
    assert added == {("scheduled_job_runs", "retry_at"), ("broadcasts", "fanout_failures")}


def test_the_downgrade_refuses_while_a_broadcast_is_failed_then_drops_them():
    recorder = _recorded("downgrade")
    assert "status = 'FAILED'" in recorder.utils.refuse_if_rows.call_args.args[0]
    dropped = {c.args for c in recorder.op.drop_column.call_args_list}
    assert dropped == {("scheduled_job_runs", "retry_at"), ("broadcasts", "fanout_failures")}
    names = [c[0] for c in recorder.mock_calls]
    assert names.index("utils.refuse_if_rows") < names.index("op.drop_column")
