"""HandoffTokenService (PRD §7.4.2, §7.5, D51).

Single-use is the property the whole handoff design rests on, so it is tested from the
attacker's side: the same link presented twice, the wrong link at the right landing, and
a link minted for someone else's case. Deps mocked, no DB.
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
from main.appodus_utils.exception.exceptions import ForbiddenException

CASE_ID = "ca5e00000000000000000000000000ab"
CUSTOMER_ID = "11111111-2222-3333-4444-555555555555"


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
    svc._verifications.get_owned = AsyncMock(return_value=SimpleNamespace(id=CASE_ID))
    return svc


def _token(intent=HandoffIntent.PAY, case_id=CASE_ID):
    return issue_handoff_token(customer_id=CUSTOMER_ID, case_id=case_id, intent=intent)


class TestIssue:
    async def test_mints_a_link_for_a_case_the_customer_owns(self):
        svc = _service()
        token = await svc.issue(CUSTOMER_ID, CASE_ID, HandoffIntent.PAY)
        assert token
        svc._verifications.get_owned.assert_awaited_once_with(CASE_ID, CUSTOMER_ID)

    async def test_refuses_to_mint_a_link_to_someone_elses_case(self):
        # Checked at issue time, so a bot-flow bug can never produce a token that points
        # somewhere the customer has no claim on.
        svc = _service()
        svc._verifications.get_owned = AsyncMock(side_effect=ForbiddenException(message="nope"))
        with pytest.raises(ForbiddenException):
            await svc.issue(CUSTOMER_ID, "someone-elses-case", HandoffIntent.PAY)


class TestRedeem:
    async def test_a_valid_link_redeems_once(self):
        svc = _service()
        claims = await svc.redeem(_token(), HandoffIntent.PAY)
        assert claims.case == CASE_ID
        assert claims.sub == CUSTOMER_ID

    async def test_the_same_link_cannot_be_redeemed_twice(self):
        # The forwarded-message case: whoever opens it second gets nothing.
        svc = _service()
        token = _token()
        await svc.redeem(token, HandoffIntent.PAY)
        with pytest.raises(HandoffTokenError):
            await svc.redeem(token, HandoffIntent.PAY)

    async def test_the_original_holder_may_reload_their_own_landing(self):
        # Single-use must not mean single-pageview (D51): a refresh or a back-navigation
        # on a phone is normal, and the grant is what distinguishes the customer who
        # redeemed the link from someone holding a forwarded copy.
        svc = _service()
        token = _token()
        first = await svc.redeem(token, HandoffIntent.PAY)
        again = await svc.redeem(token, HandoffIntent.PAY, holder_jti=first.jti)
        assert again.case == first.case
        assert again.jti == first.jti

    async def test_reloading_does_not_spend_a_second_nonce(self):
        svc = _service()
        token = _token()
        claims = await svc.redeem(token, HandoffIntent.PAY)
        await svc.redeem(token, HandoffIntent.PAY, holder_jti=claims.jti)
        assert svc._handoff_token_redemption_repo.create_return_model.await_count == 1

    async def test_a_grant_for_another_link_does_not_revive_this_one(self):
        # Holding one valid grant must not unlock every other link a forward exposed.
        svc = _service()
        other = await svc.redeem(_token(), HandoffIntent.PAY)
        spent = _token()
        await svc.redeem(spent, HandoffIntent.PAY)
        with pytest.raises(HandoffTokenError):
            await svc.redeem(spent, HandoffIntent.PAY, holder_jti=other.jti)

    async def test_a_second_link_for_the_same_case_still_works(self):
        # Single-use is per link, not per case — "get a new link" has to work.
        svc = _service()
        await svc.redeem(_token(), HandoffIntent.PAY)
        assert await svc.redeem(_token(), HandoffIntent.PAY)

    async def test_a_token_is_refused_at_the_wrong_landing(self):
        # A report link opened at the payment landing is not a payment authorization.
        svc = _service()
        with pytest.raises(HandoffTokenError):
            await svc.redeem(_token(intent=HandoffIntent.REPORT), HandoffIntent.PAY)

    async def test_a_refused_token_is_not_spent(self):
        # Presenting a link at the wrong landing must not burn it for the right one.
        svc = _service()
        token = _token(intent=HandoffIntent.UPLOAD)
        with pytest.raises(HandoffTokenError):
            await svc.redeem(token, HandoffIntent.PAY)
        assert await svc.redeem(token, HandoffIntent.UPLOAD)

    async def test_a_tampered_token_is_refused(self):
        svc = _service()
        with pytest.raises(HandoffTokenError):
            await svc.redeem(_token()[:-4] + "AAAA", HandoffIntent.PAY)

    async def test_every_failure_looks_the_same_from_outside(self):
        # Probing a link must not reveal whether it was expired, replayed, or forged.
        svc = _service()
        token = _token()
        await svc.redeem(token, HandoffIntent.PAY)

        messages = set()
        for bad in (token, _token()[:-4] + "AAAA", "not.a.token"):
            with pytest.raises(HandoffTokenError) as exc:
                await svc.redeem(bad, HandoffIntent.PAY)
            messages.add(str(exc.value))
        assert len(messages) == 1

    async def test_records_the_client_that_burned_the_link(self):
        # Pen-check trail (§7.11): which client actually spent a given nonce.
        svc = _service()
        claims = await svc.redeem(_token(), HandoffIntent.PAY, redeemed_ip="102.89.1.1")
        record = await svc.redemption_for(claims.jti)
        assert record.redeemed_ip == "102.89.1.1"
        assert record.case_id == CASE_ID
