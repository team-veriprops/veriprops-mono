"""ChargebackService (§6a): idempotent flag freezes commissions + flags the payment
without touching the verification state machine; resolve won/lost resumes/reverses.
Repos + commission service mocked, no DB."""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.audit.models import AuditActionType
from main.app.domain.payment.chargeback.models import (
    ChargebackStatus,
    ChargebackWebhookDto,
)
from main.app.domain.payment.chargeback.service import ChargebackService
from main.app.domain.payment.models import PaymentStatus
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import (
    InvalidResourceStateException,
    ResourceNotFoundException,
)


@pytest.fixture(autouse=True)
def mock_db_session():
    session = MagicMock()
    session.in_transaction.return_value = False

    @asynccontextmanager
    async def _begin():
        yield

    session.begin = _begin
    session.flush = AsyncMock()
    token = db_session_ctx.set(session)
    yield session
    db_session_ctx.reset(token)


def _payment(pid="p-1"):
    return SimpleNamespace(
        id=pid, verification_id="v-1", customer_id="cust-1", tx_ref="TX-1",
        amount_minor=1000000, currency="NGN",
    )


def _chargeback(status=ChargebackStatus.FLAGGED, cbid="cb-1"):
    return SimpleNamespace(
        id=cbid, payment_id="p-1", verification_id="v-1", gateway_event_id="evt-1",
        status=status.value, reason="fraud", amount_minor=1000000, currency="NGN",
        rebuttal_pack=None, resolved_at=None,
    )


def _make_service(*, existing_cb=None, payment=None, chargebacks=None):
    svc = object.__new__(ChargebackService)
    svc._repo = MagicMock()
    svc._payment_repo = MagicMock()
    svc._verification_repo = MagicMock()
    svc._commissions = MagicMock()
    svc._consent_service = MagicMock()
    svc._audit_repo = MagicMock()
    svc._audit = MagicMock()

    state = {"rows": list(chargebacks or [])}
    svc._repo.get_by_event_id = AsyncMock(return_value=existing_cb)
    svc._payment_repo.get_by_tx_ref = AsyncMock(return_value=payment)
    svc._payment_repo.update = AsyncMock()

    async def _create(dto):
        cb = _chargeback()
        cb.status = dto.status.value if hasattr(dto.status, "value") else dto.status
        cb.rebuttal_pack = dto.rebuttal_pack
        state["rows"].append(cb)
        return cb

    async def _get_model(cbid):
        return next((c for c in state["rows"] if c.id == cbid), None)

    async def _update(cbid, dto):
        c = next((c for c in state["rows"] if c.id == cbid), None)
        if c is not None:
            for f, v in dto.model_dump(exclude_none=True).items():
                setattr(c, f, v)
        return c

    svc._repo.create_return_model = AsyncMock(side_effect=_create)
    svc._repo.get_model = AsyncMock(side_effect=_get_model)
    svc._repo.update = AsyncMock(side_effect=_update)
    svc._commissions.freeze_for_verification = AsyncMock(return_value=2)
    svc._commissions.unfreeze_for_verification = AsyncMock(return_value=2)
    svc._commissions.reverse_for_verification = AsyncMock(return_value=2)
    # Private (excluded from decorators) — stub the pack assembly.
    svc._assemble_rebuttal_pack = AsyncMock(return_value={"stub": True})
    svc._state = state
    return svc


class TestHandleWebhook:
    async def test_flag_freezes_commissions_and_flags_payment(self):
        svc = _make_service(payment=_payment())
        cb = await svc.handle_webhook(ChargebackWebhookDto(event_id="evt-1", tx_ref="TX-1", reason="fraud"))
        assert cb.status == ChargebackStatus.FLAGGED.value
        svc._commissions.freeze_for_verification.assert_awaited_once()
        # payment flagged (not the verification state machine)
        svc._payment_repo.update.assert_awaited()

    async def test_idempotent_on_event_id(self):
        existing = _chargeback()
        svc = _make_service(existing_cb=existing, payment=_payment())
        cb = await svc.handle_webhook(ChargebackWebhookDto(event_id="evt-1", tx_ref="TX-1"))
        assert cb is existing
        svc._commissions.freeze_for_verification.assert_not_awaited()

    async def test_missing_payment_raises(self):
        svc = _make_service(payment=None)
        with pytest.raises(ResourceNotFoundException):
            await svc.handle_webhook(ChargebackWebhookDto(event_id="evt-9", tx_ref="NOPE"))


class TestSubmitRebuttal:
    async def test_only_flagged_can_be_rebutted(self):
        svc = _make_service(chargebacks=[_chargeback(ChargebackStatus.WON)])
        with pytest.raises(InvalidResourceStateException):
            await svc.submit_rebuttal("cb-1", "admin-1")

    async def test_transitions_to_rebuttal_submitted(self):
        svc = _make_service(chargebacks=[_chargeback(ChargebackStatus.FLAGGED)])
        cb = await svc.submit_rebuttal("cb-1", "admin-1")
        assert cb.status == ChargebackStatus.REBUTTAL_SUBMITTED.value


class TestResolve:
    async def test_won_resumes_commissions(self):
        svc = _make_service(chargebacks=[_chargeback(ChargebackStatus.REBUTTAL_SUBMITTED)])
        cb = await svc.resolve("cb-1", won=True, admin_id="admin-1")
        assert cb.status == ChargebackStatus.WON.value
        svc._commissions.unfreeze_for_verification.assert_awaited_once()

    async def test_lost_reverses_commissions_and_fails_payment(self):
        svc = _make_service(chargebacks=[_chargeback(ChargebackStatus.REBUTTAL_SUBMITTED)])
        cb = await svc.resolve("cb-1", won=False, admin_id="admin-1")
        assert cb.status == ChargebackStatus.LOST.value
        svc._commissions.reverse_for_verification.assert_awaited_once()
        # payment marked failed on the reversal
        update_dtos = [c.args[1] for c in svc._payment_repo.update.call_args_list]
        assert any(getattr(d, "status", None) == PaymentStatus.FAILED.value for d in update_dtos)

    async def test_already_resolved_rejected(self):
        svc = _make_service(chargebacks=[_chargeback(ChargebackStatus.WON)])
        with pytest.raises(InvalidResourceStateException):
            await svc.resolve("cb-1", won=True, admin_id="admin-1")

    async def test_won_audits(self):
        svc = _make_service(chargebacks=[_chargeback(ChargebackStatus.REBUTTAL_SUBMITTED)])
        await svc.resolve("cb-1", won=True, admin_id="admin-1")
        actions = [c.kwargs["action"] for c in svc._audit.schedule.call_args_list]
        assert AuditActionType.CHARGEBACK_WON in actions
