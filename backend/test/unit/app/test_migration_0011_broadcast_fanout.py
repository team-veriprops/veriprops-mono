"""Migration 0011 gives a broadcast a fan-out cursor and a count of recipients reached.

It must chain after 0010, add exactly the two columns the model declares (the
cursor nullable, the count defaulting to 0 so existing broadcasts read as "none reached"), and
drop only those on the way down — refusing while a broadcast is mid-send, because dropping its
cursor would strand it half-delivered with nothing to resume from.
"""
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

from alembic.config import Config
from alembic.script import ScriptDirectory

from main.app.domain.broadcast.models import Broadcast

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_REVISION = "0011_broadcast_fanout"
_MIGRATION = _BACKEND_ROOT / "main" / "alembic" / "versions" / f"{_REVISION}.py"


def _scripts() -> ScriptDirectory:
    config = Config()
    config.set_main_option("script_location", str(_BACKEND_ROOT / "main" / "alembic"))
    return ScriptDirectory.from_config(config)


def _recorded(step: str):
    spec = importlib.util.spec_from_file_location("migration_0011", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    recorder = MagicMock()
    module.op, module.AlembicUtils = recorder.op, recorder.utils
    getattr(module, step)()
    return recorder


def test_it_chains_after_the_job_clock_migration():
    assert _scripts().get_revision(_REVISION).down_revision == "0010_scheduled_job_runs"


def test_the_model_declares_both_columns():
    table = Broadcast.__table__
    assert table.c.fanout_cursor.nullable is True and table.c.fanout_cursor.type.length == 36
    assert table.c.recipients_enqueued.nullable is False
    assert str(table.c.recipients_enqueued.server_default.arg) == "0"


def test_the_upgrade_adds_the_two_columns():
    op = _recorded("upgrade").op
    added = {call.args[1].name: call.args[1] for call in op.add_column.call_args_list}
    assert all(call.args[0] == "broadcasts" for call in op.add_column.call_args_list)
    assert set(added) == {"fanout_cursor", "recipients_enqueued"}
    assert added["fanout_cursor"].nullable is True
    assert added["recipients_enqueued"].nullable is False


def test_the_downgrade_refuses_while_a_broadcast_is_mid_send_then_drops_only_those_columns():
    recorder = _recorded("downgrade")
    count_sql = recorder.utils.refuse_if_rows.call_args.args[0]
    assert "status = 'SENDING'" in count_sql
    dropped = {call.args for call in recorder.op.drop_column.call_args_list}
    assert dropped == {("broadcasts", "fanout_cursor"), ("broadcasts", "recipients_enqueued")}
    names = [c[0] for c in recorder.mock_calls]
    assert names.index("utils.refuse_if_rows") < names.index("op.drop_column")
