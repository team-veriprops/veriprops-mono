"""Migration 0004 gives payouts a real transfer trail, additively.

It must chain directly after the payment-gateway-reference migration, leave the history with a
single head, and create exactly the columns and the unique reference index the ORM declares —
a webhook finds its payout by that reference, and one reference is one transfer attempt.
"""
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from main.app.domain.payout.bank_account.models import AgentBankAccount
from main.app.domain.payout.models import Payout

_BACKEND_ROOT = Path(__file__).resolve().parents[3]


def _scripts() -> ScriptDirectory:
    config = Config()
    config.set_main_option("script_location", str(_BACKEND_ROOT / "main" / "alembic"))
    return ScriptDirectory.from_config(config)


def test_it_chains_after_the_gateway_reference_migration_and_is_the_only_head():
    scripts = _scripts()
    assert scripts.get_heads() == ["0004_payout_transfers"]
    assert scripts.get_revision("0004_payout_transfers").down_revision == "0003_payment_gateway_ref"


def test_the_models_declare_what_the_migration_creates():
    payouts = Payout.__table__.c
    for name in ("bank_code", "provider", "transfer_reference", "gateway_transfer_id",
                 "sent_at", "settled_at", "failure_reason"):
        assert payouts[name].nullable is True, name
    assert payouts.fee_minor.nullable is False
    assert payouts.transfer_attempts.nullable is False
    assert (payouts.transfer_reference.type.length, payouts.bank_code.type.length) == (64, 16)
    reference_index = {i.name: i for i in Payout.__table__.indexes}["ix_payouts_transfer_reference"]
    assert reference_index.unique is True

    accounts = AgentBankAccount.__table__.c
    assert accounts.bank_code.nullable is True
    assert accounts.provider.nullable is True
