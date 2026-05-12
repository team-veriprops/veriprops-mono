"""Unit tests for PayoutService (S48)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from main.app.domain.payout.models import (
    AdjustPayoutDto,
    HoldPayoutDto,
    PayoutStatus,
    WithdrawalRequestDto,
)
from main.app.domain.payout.service import PayoutService
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import ValidationException


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


def _mock_bank(bank_id="bank-1", agent_id="agent-1"):
    b = MagicMock()
    b.id = bank_id
    b.agent_id = agent_id
    b.bank_name = "GTBank"
    b.account_number = "0123456789"
    b.account_holder_name = "John Doe"
    b.is_default = True
    b.date_created = str(datetime.now(timezone.utc))
    return b


def _mock_payout(payout_id="pay-1", agent_id="agent-1", amount=500.0, status=PayoutStatus.PENDING.value):
    p = MagicMock()
    p.id = payout_id
    p.agent_id = agent_id
    p.amount = amount
    p.bank_account_id = "bank-1"
    p.status = status
    p.requested_at = str(datetime.now(timezone.utc))
    p.approved_at = None
    p.paid_at = None
    p.hold_reason = None
    p.date_created = str(datetime.now(timezone.utc))
    return p


def _make_svc(payout=None, bank=None):
    payout_repo = MagicMock()
    payout_repo.create = AsyncMock(return_value=payout or _mock_payout())
    payout_repo.get_model = AsyncMock(return_value=payout or _mock_payout())
    payout_repo.update = AsyncMock()
    payout_repo.list_for_agent = AsyncMock(return_value=[])
    payout_repo.get_all = AsyncMock(return_value=[])

    bank_repo = MagicMock()
    bank_repo.get_model = AsyncMock(return_value=bank or _mock_bank())
    bank_repo.list_for_agent = AsyncMock(return_value=[])
    bank_repo.create = AsyncMock(return_value=bank or _mock_bank())

    adjustment_repo = MagicMock()
    adjustment_repo.create = AsyncMock()

    svc = PayoutService(payout_repo=payout_repo, bank_repo=bank_repo, adjustment_repo=adjustment_repo)
    return svc, payout_repo, bank_repo, adjustment_repo


class TestSubmitWithdrawal:
    async def test_exceeds_available_balance_raises(self):
        svc, _, _, _ = _make_svc()

        commission_svc = MagicMock()
        commission_svc.available_balance = AsyncMock(return_value=Decimal("50.00"))

        with patch("main.app.domain.payout.service.di") as mock_di:
            mock_di.__getitem__ = MagicMock(return_value=commission_svc)
            with pytest.raises(ValidationException, match="exceeds available balance"):
                await svc.submit_withdrawal(
                    "agent-1",
                    WithdrawalRequestDto(amount=200.0, bank_account_id="bank-1"),
                )

    async def test_within_balance_creates_payout(self):
        svc, payout_repo, _, _ = _make_svc()

        commission_svc = MagicMock()
        commission_svc.available_balance = AsyncMock(return_value=Decimal("1000.00"))

        with patch("main.app.domain.payout.service.di") as mock_di:
            mock_di.__getitem__ = MagicMock(return_value=commission_svc)
            result = await svc.submit_withdrawal(
                "agent-1",
                WithdrawalRequestDto(amount=500.0, bank_account_id="bank-1"),
            )

        payout_repo.create.assert_called_once()
        call_dto = payout_repo.create.call_args[0][0]
        assert call_dto.amount == 500.0
        assert call_dto.status == PayoutStatus.PENDING.value


class TestAdjust:
    async def test_creates_adjustment_with_original_amount(self):
        payout = _mock_payout(amount=500.0)
        svc, _, _, adjustment_repo = _make_svc(payout=payout)

        with patch.object(svc, "_notify_safe", AsyncMock()):
            await svc.adjust(
                "pay-1",
                AdjustPayoutDto(new_amount=400.0, reason="Corrected amount"),
                "admin-1",
            )

        adjustment_repo.create.assert_called_once()
        call_dto = adjustment_repo.create.call_args[0][0]
        assert call_dto.original_amount == 500.0
        assert call_dto.new_amount == 400.0
        assert call_dto.reason == "Corrected amount"


class TestApprove:
    async def test_approve_sets_status_to_approved(self):
        svc, payout_repo, _, _ = _make_svc()

        with patch.object(svc, "_notify_safe", AsyncMock()):
            await svc.approve("pay-1", "admin-1")

        payout_repo.update.assert_called_once()
        call_dto = payout_repo.update.call_args[0][1]
        assert call_dto.status == PayoutStatus.APPROVED.value
