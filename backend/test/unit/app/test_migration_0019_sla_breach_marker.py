"""Migration 0019: the SLA-breach marker the sweep claims before it notifies.

Pinned with no database, from the SQL the migration emits offline both ways: the column is
added, verifications already announced are marked from their existing notifications (so the
switch-over sends nobody a second "taking longer" message), and downgrade removes it.
"""
import importlib.util
import io
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from main.app.domain.verification.models import Verification

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_MIGRATION = _BACKEND_ROOT / "main" / "alembic" / "versions" / "0019_sla_breach_marker.py"
_FROM, _TO = "0018_concurrency_constraints", "0019_sla_breach_marker"


def _migration():
    spec = importlib.util.spec_from_file_location("migration_0019", _MIGRATION)
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


@pytest.fixture(scope="module")
def upgrade_sql() -> str:
    return _offline_sql("upgrade")


def test_it_follows_0018():
    module = _migration()
    assert (module.revision, module.down_revision) == (_TO, _FROM)


def test_it_adds_a_nullable_timestamp(upgrade_sql):
    assert "ALTER TABLE verifications ADD COLUMN sla_breach_notified_at TIMESTAMP WITH TIME ZONE" in upgrade_sql


def test_verifications_already_announced_are_marked_from_their_first_notification(upgrade_sql):
    assert "UPDATE verifications" in upgrade_sql
    assert "SET sla_breach_notified_at = announced.first_at" in upgrade_sql
    assert "WHERE type = 'SLA_BREACHED'" in upgrade_sql
    # Notifications reference the verification by its hex id (`Utils.uuid_to_hex`).
    assert "replace(verifications.id::text, '-', '') = announced.event_ref" in upgrade_sql
    # The backfill runs after the column exists.
    assert upgrade_sql.index("ADD COLUMN sla_breach_notified_at") < upgrade_sql.index("UPDATE verifications")


def test_downgrade_drops_it():
    assert "ALTER TABLE verifications DROP COLUMN sla_breach_notified_at" in _offline_sql("downgrade")


def test_the_model_declares_it():
    column = Verification.__table__.columns["sla_breach_notified_at"]
    assert column.nullable
