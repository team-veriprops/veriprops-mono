"""Migration 0007 adds the refund-approval queue, what a charge still owes, and why a case closed.

It must chain after 0006, create what the models declare, and backfill what
today's refunds-to-retry list shows as owed — so no refused refund drops off Finance's list.
"""
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from main.app.domain.payment.models import Payment
from main.app.domain.payment.refund_request.models import RefundRequest
from main.app.domain.verification.models import Verification

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_MIGRATION = _BACKEND_ROOT / "main" / "alembic" / "versions" / "0007_refund_requests.py"


def _scripts() -> ScriptDirectory:
    config = Config()
    config.set_main_option("script_location", str(_BACKEND_ROOT / "main" / "alembic"))
    return ScriptDirectory.from_config(config)


def test_it_chains_after_the_kyc_images_migration():
    assert _scripts().get_revision("0007_refund_requests").down_revision == "0006_kyc_images"


def test_the_models_declare_what_the_migration_creates():
    assert Payment.__table__.c.refund_due_minor.nullable is True
    assert Verification.__table__.c.closure_reason.type.length == 32
    pending = next(i for i in RefundRequest.__table__.indexes if i.name == "uq_refund_requests_pending_verification")
    assert pending.unique and [c.name for c in pending.columns] == ["verification_id"]


def test_the_backfill_keeps_every_refund_the_old_list_showed_as_owed():
    source = _MIGRATION.read_text(encoding="utf-8")
    assert "SET refund_due_minor = p.amount_minor" in source
    for condition in ("p.status = 'SUCCEEDED'", "p.chargeback_status IS NULL", "v.status IN ('FAILED', 'REFUNDED')"):
        assert condition in source
