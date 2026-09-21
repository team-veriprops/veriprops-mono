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

from main.app.domain.channel.whatsapp.bot.surface import WhatsAppAssistantSurface
from main.app.domain.communication.assistant import content
from main.app.domain.communication.assistant.engine import AssistantEngine
from main.app.domain.communication.assistant.flows import status as status_flow
from main.app.domain.communication.assistant.projection import ChannelState
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


def _pair(*, user_id=None, delegate=None, case=None):
    """The engine and WhatsApp surface, wired only as far as the identity fork - that is
    what is under test. The surface resolves who is asking (D67); the engine answers them."""
    sessions = MagicMock(clear_flow=AsyncMock(), enter_flow=AsyncMock(), note_understood=AsyncMock())

    engine = object.__new__(AssistantEngine)
    engine._sessions = sessions
    engine._load_case = AsyncMock(return_value=case)
    engine.load_cases = AsyncMock(return_value=[_case()])

    surface = object.__new__(WhatsAppAssistantSurface)
    surface._sessions = sessions
    surface._whatsapp_link_service = MagicMock(
        resolve_user_for_phone=AsyncMock(return_value=user_id)
    )
    surface._case_delegate_service = MagicMock(
        resolve_delegate_for_phone=AsyncMock(return_value=delegate),
        revoke_by_phone=AsyncMock(return_value=delegate),
    )
    surface._whatsapp_consent_service = MagicMock(revoke_all=AsyncMock())
    return engine, surface


def _session():
    return SimpleNamespace(phone_e164=PHONE, context={})


async def _status(engine, surface):
    party = await surface._resolve_party(PHONE)
    return await engine._status(_session(), party, surface)


class TestResolutionOrder:
    async def test_a_linked_account_never_reaches_the_delegate_lookup(self):
        """D67: `resolve_user_for_phone` stays the channel's single account lookup, and
        the delegate lookup sits beside it - asked only when it answers None."""
        engine, surface = _pair(user_id="cust-1", delegate=_delegate(), case=_case())
        await _status(engine, surface)
        surface._case_delegate_service.resolve_delegate_for_phone.assert_not_called()

    async def test_a_number_that_is_both_resolves_as_the_customer(self):
        """The account grant is strictly wider. Reading it as a delegate would show a
        customer one of their own cases and hide the rest."""
        engine, surface = _pair(user_id="cust-1", delegate=_delegate(), case=_case())
        reply = await _status(engine, surface)
        engine.load_cases.assert_awaited_once()
        assert "as a delegate" not in reply.text


class TestDelegateStatus:
    async def test_a_verified_delegate_gets_their_one_case(self):
        engine, surface = _pair(delegate=_delegate(), case=_case())
        reply = await _status(engine, surface)
        assert VID in reply.text
        assert "as a delegate" in reply.text

    async def test_the_delegate_is_named_by_role(self):
        """Section 26.4.5 requires the assistant to identify them as a delegate - partly so
        the next answer, which routes their other questions away, is not a surprise."""
        engine, surface = _pair(delegate=_delegate(name="Bola"), case=_case())
        reply = await _status(engine, surface)
        assert "Bola" in reply.text

    async def test_a_delegate_is_never_offered_a_report_or_a_login(self):
        """The customer's own copy ends "sign in for the full details and your report".
        A delegate has neither, so offering one promises access the design refuses."""
        engine, surface = _pair(delegate=_delegate(), case=_case())
        reply = await _status(engine, surface)
        assert "your report" not in reply.text.lower()
        assert "sign in" not in reply.text.lower()

    async def test_a_delegate_reads_only_the_case_they_were_granted(self):
        """The case comes from the delegation row, never from the customer's list and
        never from a reference the delegate types."""
        engine, surface = _pair(delegate=_delegate(verification_id="case-9"), case=_case())
        await _status(engine, surface)
        engine._load_case.assert_awaited_once_with("case-9")
        engine.load_cases.assert_not_called()

    async def test_a_delegation_whose_case_has_gone_falls_back_to_a_new_enquiry(self):
        """Inventing a status for a case that no longer exists would be worse than
        treating the person as a stranger."""
        engine, surface = _pair(delegate=_delegate(), case=None)
        reply = await _status(engine, surface)
        assert reply.text == content.unlinked_number()


class TestThirdParties:
    async def test_a_stranger_is_told_nothing_about_any_case(self):
        engine, surface = _pair()
        reply = await _status(engine, surface)
        assert VID not in reply.text
        assert "12 Admiralty Way" not in reply.text

    async def test_a_stranger_is_pointed_at_both_legitimate_routes(self):
        """The "my relative is handling it" script is what section 26.4.5 exists to defeat,
        so the refusal has to be warm *and* actionable - otherwise the pressure just moves to
        an agent.

        One message, both routes, because the assistant cannot tell a stranger from a
        customer on a second handset and must not guess: sending the stranger through
        linking wastes an OTP on an account without this case, and sending the customer to
        ask a delegate's permission for their own verification is worse.
        """
        reply_text = content.unlinked_number()
        assert "delegate" in reply_text.lower()
        assert "link my account" in reply_text.lower()


class TestDelegateStop:
    async def test_stop_from_a_delegate_ends_the_delegation(self):
        """D77: a delegate has no consent row, so this is the only lever that actually
        stops the messages."""
        engine, surface = _pair(delegate=_delegate())
        party = await surface._resolve_party(PHONE)
        reply = await surface.consent_keyword(engine, _session(), party, stop=True)
        surface._case_delegate_service.revoke_by_phone.assert_awaited_once_with(PHONE)
        surface._whatsapp_consent_service.revoke_all.assert_not_called()
        assert "won't receive" in reply.text

    async def test_stop_from_a_customer_still_revokes_consent_not_a_delegation(self):
        engine, surface = _pair(user_id="cust-1", delegate=_delegate())
        party = await surface._resolve_party(PHONE)
        await surface.consent_keyword(engine, _session(), party, stop=True)
        surface._whatsapp_consent_service.revoke_all.assert_awaited_once()
        surface._case_delegate_service.revoke_by_phone.assert_not_called()


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
