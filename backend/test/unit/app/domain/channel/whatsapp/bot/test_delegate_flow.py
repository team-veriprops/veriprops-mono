"""The bot's delegate branch (PRD §26.4.5, D67/D77; WA-26).

§26.4.5 exists to defeat one sentence — "my relative is handling it" — so these tests are
about who the bot answers and with what. Three outcomes, and the order between them *is*
the access control (D67):

1. the number is a linked account → the customer's own flow, unchanged;
2. otherwise a verified delegation → that one case, status only, no report link;
3. otherwise a stranger → warm, and told nothing.

The overlap case gets its own test because getting it backwards is the expensive mistake:
a number that is both must resolve as the customer, since the account grant is strictly
wider and reading it as a delegate would lose that person access to their own data.
"""
from contextlib import asynccontextmanager
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.channel.whatsapp.bot import content
from main.app.domain.channel.whatsapp.bot.engine import WhatsAppBotEngine
from main.app.domain.channel.whatsapp.bot.flows import status as status_flow
from main.app.domain.channel.whatsapp.bot.projection import ChannelState
from main.appodus_utils.db.session import db_session_ctx

PHONE = "+2348012345678"
VID = "VP-2026-0042"


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


def _case(vid=VID) -> status_flow.CaseSummary:
    return status_flow.CaseSummary(
        vid=vid,
        property_label="12 Admiralty Way, Lekki",
        status_label="In Progress",
        channel_state=ChannelState.VERIFYING,
        sla_due_date=date(2026, 9, 15),
    )


def _delegate(name="Tunde", verification_id="case-1"):
    return SimpleNamespace(name=name, verification_id=verification_id, phone_e164=PHONE)


def _engine(*, user_id=None, delegate=None, case=None):
    """An engine wired only as far as the identity fork — that is what is under test."""
    engine = object.__new__(WhatsAppBotEngine)
    engine._whatsapp_link_service = MagicMock(
        resolve_user_for_phone=AsyncMock(return_value=user_id)
    )
    engine._case_delegate_service = MagicMock(
        resolve_delegate_for_phone=AsyncMock(return_value=delegate),
        revoke_by_phone=AsyncMock(return_value=delegate),
    )
    engine._whatsapp_bot_session_service = MagicMock(
        clear_flow=AsyncMock(), enter_flow=AsyncMock(), note_understood=AsyncMock(),
    )
    engine._load_case = AsyncMock(return_value=case)
    engine._load_cases = AsyncMock(return_value=[_case()])
    return engine


def _session():
    return SimpleNamespace(phone_e164=PHONE, context={})


class TestResolutionOrder:
    async def test_a_linked_account_never_reaches_the_delegate_lookup(self):
        """D67: `resolve_user_for_phone` stays the channel's single account lookup, and
        the delegate lookup sits beside it — asked only when it answers None."""
        engine = _engine(user_id="cust-1", delegate=_delegate(), case=_case())
        await engine._status(_session())
        engine._case_delegate_service.resolve_delegate_for_phone.assert_not_called()

    async def test_a_number_that_is_both_resolves_as_the_customer(self):
        """The account grant is strictly wider. Reading it as a delegate would show a
        customer one of their own cases and hide the rest."""
        engine = _engine(user_id="cust-1", delegate=_delegate(), case=_case())
        reply = await engine._status(_session())
        engine._load_cases.assert_awaited_once()
        assert "as a delegate" not in reply.text


class TestDelegateStatus:
    async def test_a_verified_delegate_gets_their_one_case(self):
        engine = _engine(delegate=_delegate(), case=_case())
        reply = await engine._status(_session())
        assert VID in reply.text
        assert "as a delegate" in reply.text

    async def test_the_delegate_is_named_by_role(self):
        """§26.4.5 requires the bot to identify them as a delegate — partly so the next
        answer, which routes their other questions away, is not a surprise."""
        engine = _engine(delegate=_delegate(name="Bola"), case=_case())
        reply = await engine._status(_session())
        assert "Bola" in reply.text

    async def test_a_delegate_is_never_offered_a_report_or_a_login(self):
        """The customer's own copy ends "sign in for the full details and your report".
        A delegate has neither, so offering one promises access the design refuses."""
        engine = _engine(delegate=_delegate(), case=_case())
        reply = await engine._status(_session())
        assert "your report" not in reply.text.lower()
        assert "sign in" not in reply.text.lower()

    async def test_a_delegate_reads_only_the_case_they_were_granted(self):
        """The case comes from the delegation row, never from the customer's list and
        never from a reference the delegate types."""
        engine = _engine(delegate=_delegate(verification_id="case-9"), case=_case())
        await engine._status(_session())
        engine._load_case.assert_awaited_once_with("case-9")
        engine._load_cases.assert_not_called()

    async def test_a_delegation_whose_case_has_gone_falls_back_to_a_new_enquiry(self):
        """Inventing a status for a case that no longer exists would be worse than
        treating the person as a stranger."""
        engine = _engine(delegate=_delegate(), case=None)
        reply = await engine._status(_session())
        assert reply.text == content.unlinked_number()


class TestThirdParties:
    async def test_a_stranger_is_told_nothing_about_any_case(self):
        engine = _engine()
        reply = await engine._status(_session())
        assert VID not in reply.text
        assert "12 Admiralty Way" not in reply.text

    async def test_a_stranger_is_pointed_at_both_legitimate_routes(self):
        """"My relative is handling it" is the script §26.4.5 exists to defeat, so the
        refusal has to be warm *and* actionable — otherwise the pressure just moves to
        an agent.

        One message, both routes, because the bot cannot tell a stranger from a customer
        on a second handset and must not guess: sending the stranger through linking
        wastes an OTP on an account without this case, and sending the customer to ask a
        delegate's permission for their own verification is worse.
        """
        reply_text = content.unlinked_number()
        assert "delegate" in reply_text.lower()
        assert "link my account" in reply_text.lower()


class TestDelegateStop:
    async def test_stop_from_a_delegate_ends_the_delegation(self):
        """D77: a delegate has no consent row, so this is the only lever that actually
        stops the messages."""
        engine = _engine(delegate=_delegate())
        engine._whatsapp_consent_service = MagicMock(revoke_all=AsyncMock())
        reply = await engine._stop_messages(_session())
        engine._case_delegate_service.revoke_by_phone.assert_awaited_once_with(PHONE)
        engine._whatsapp_consent_service.revoke_all.assert_not_called()
        assert "won't receive" in reply.text

    async def test_stop_from_a_customer_still_revokes_consent_not_a_delegation(self):
        engine = _engine(user_id="cust-1", delegate=_delegate())
        engine._whatsapp_consent_service = MagicMock(revoke_all=AsyncMock())
        await engine._stop_messages(_session())
        engine._whatsapp_consent_service.revoke_all.assert_awaited_once()
        engine._case_delegate_service.revoke_by_phone.assert_not_called()


class TestRenderForDelegate:
    def test_it_carries_no_link_of_any_kind(self):
        """Structural, not incidental: there is no code path from this function to a
        report, an upload page or a portal deep link."""
        text = status_flow.render_for_delegate(_case(), "Tunde").text
        assert "http" not in text
        assert "/wa/" not in text

    def test_it_never_awaits_a_choice(self):
        """A delegate holds exactly one case, so there is nothing to disambiguate and no
        flow to park."""
        outcome = status_flow.render_for_delegate(_case(), "Tunde")
        assert outcome.awaits_choice is False

    def test_it_says_where_the_other_questions_go(self):
        text = status_flow.render_for_delegate(_case(), "Tunde").text
        assert "account holder" in text.lower()
