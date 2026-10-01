"""Migration 0003 adds the provider-neutral gateway reference to payments, additively.

It must chain directly after the fixed-commission migration and create exactly the column and
index the ORM model declares. (That the history has a single head is pinned by the newest
migration's own test.)
"""
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from main.app.domain.payment.models import Payment

_BACKEND_ROOT = Path(__file__).resolve().parents[3]


def _scripts() -> ScriptDirectory:
    config = Config()
    config.set_main_option("script_location", str(_BACKEND_ROOT / "main" / "alembic"))
    return ScriptDirectory.from_config(config)


def test_it_chains_after_the_commission_migration():
    scripts = _scripts()
    assert scripts.get_revision("0003_payment_gateway_ref").down_revision == "0002_fixed_agent_commission"


def test_the_model_declares_what_the_migration_creates():
    column = Payment.__table__.c.gateway_reference
    assert column.nullable is True
    assert column.type.length == 128
    assert "ix_payments_gateway_reference" in {index.name for index in Payment.__table__.indexes}
