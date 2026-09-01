"""Link-token handling on HandoffTokenService (PRD §7.4.4, D55).

A `link` token is the weakest thing the token service mints: it names a phone number and
nothing else, and on its own it unlocks nothing — the OTP that follows is what proves the
number. What it must still guarantee is that the bot's invitation cannot be *reused*, and
that it can never be mistaken for authority over a case.
"""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.channel.whatsapp.handoff.models import HandoffIntent
from main.app.domain.channel.whatsapp.handoff.service import HandoffTokenService
from main.app.domain.channel.whatsapp.handoff.tokens import (
    HandoffTokenError,
    issue_handoff_token,
)
from main.appodus_utils.db.session import db_session_ctx

CASE_ID = "ca5e00000000000000000000000000ab"
CUSTOMER_ID = "11111111-2222-3333-4444-555555555555"
PHONE = "+2348012345678"


@pytest.fixture(autouse=True)
def mock_db_session():
    session = MagicMock()
    session.in_transaction.return_value = False

    @asynccontextmanager
    async def _begin():
        yield

    session.begin = _begin
    session.flush = AsyncMock()
    session.add = MagicMock()
    token = db_session_ctx.set(session)
    yield session
    db_session_ctx.reset(token)


def _service():
    """A service whose ledger behaves like the real unique index: first write wins."""
    svc = object.__new__(HandoffTokenService)
    svc._handoff_token_redemption_repo = MagicMock()
    svc._verifications = MagicMock()
    spent: dict = {}

    async def _get_by_jti(jti):
        return spent.get(jti)

    async def _create(dto):
        row = SimpleNamespace(**dto.model_dump())
        spent[dto.jti] = row
        return row

    svc._handoff_token_redemption_repo.get_by_jti = AsyncMock(side_effect=_get_by_jti)
    svc._handoff_token_redemption_repo.create_return_model = AsyncMock(side_effect=_create)
    return svc


class TestIssueLink:
    async def test_mints_a_link_for_a_number_with_no_account(self):
        # Deliberately no ownership check: the number belongs to nobody yet, which is
        # exactly why the bot is sending this.
        svc = _service()
        claims = await svc.decode_link(await svc.issue_link(PHONE))
        assert claims.intent == HandoffIntent.LINK
        assert claims.phone == PHONE


class TestDecodeLink:
    async def test_reading_a_link_does_not_spend_it(self):
        # Starting a linking attempt must survive a resend: burning the nonce here would
        # strand a customer whose first code never arrived.
        svc = _service()
        token = await svc.issue_link(PHONE)
        await svc.decode_link(token)
        assert await svc.decode_link(token)

    async def test_refuses_a_link_that_has_already_been_completed(self):
        svc = _service()
        token = await svc.issue_link(PHONE)
        await svc.redeem_link(token)
        with pytest.raises(HandoffTokenError):
            await svc.decode_link(token)

    async def test_refuses_an_action_token(self):
        svc = _service()
        action = issue_handoff_token(
            customer_id=CUSTOMER_ID, case_id=CASE_ID, intent=HandoffIntent.PAY
        )
        with pytest.raises(HandoffTokenError):
            await svc.decode_link(action)


class TestRedeemLink:
    async def test_one_completed_link_per_invitation(self):
        svc = _service()
        token = await svc.issue_link(PHONE)
        assert (await svc.redeem_link(token)).phone == PHONE
        with pytest.raises(HandoffTokenError):
            await svc.redeem_link(token)

    async def test_the_ledger_records_the_number_instead_of_a_case(self):
        # §7.11 pen-check trail: a link redemption names no case, so the number is the
        # only thing that identifies what was spent.
        svc = _service()
        claims = await svc.redeem_link(await svc.issue_link(PHONE), redeemed_ip="102.89.1.1")
        record = await svc.redemption_for(claims.jti)
        assert record.case_id is None
        assert record.phone_e164 == PHONE
        assert record.redeemed_ip == "102.89.1.1"

    async def test_an_action_token_cannot_be_spent_as_a_link(self):
        svc = _service()
        action = issue_handoff_token(
            customer_id=CUSTOMER_ID, case_id=CASE_ID, intent=HandoffIntent.PAY
        )
        with pytest.raises(HandoffTokenError):
            await svc.redeem_link(action)

    async def test_a_link_token_cannot_be_spent_at_a_payment_landing(self):
        svc = _service()
        token = await svc.issue_link(PHONE)
        with pytest.raises(HandoffTokenError):
            await svc.redeem(token, HandoffIntent.PAY)
