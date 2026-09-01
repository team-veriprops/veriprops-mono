"""WhatsAppLinkService (PRD §7.4.4, WA-23/WA-24/WA-25).

The channel's identity seam, so these are written adversarially. Every flow that could
leak case data to a stranger's phone asks `resolve_user_for_phone`, which means the tests
that matter most are the ones proving it stays silent: a pending attempt is not a link, a
revoked one is not a link, and a number that changed hands does not answer for the account
it used to belong to.

Deps mocked, no DB.
"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.audit.models import AuditActionType
from main.app.domain.channel.whatsapp.handoff.models import HandoffIntent
from main.app.domain.channel.whatsapp.handoff.tokens import HandoffTokenError
from main.app.domain.channel.whatsapp.link.models import WhatsAppLinkStatus
from main.app.domain.channel.whatsapp.link.service import (
    NUMBER_UNAVAILABLE_MESSAGE,
    WhatsAppLinkService,
)
from main.app.domain.user.auth.models import OtpChannel
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import (
    ResourceNotFoundException,
    ValidationException,
)

USER_ID = "11111111-2222-3333-4444-555555555555"
OTHER_USER_ID = "99999999-8888-7777-6666-555555555555"
PHONE = "+2348012345678"
OTHER_PHONE = "+2348099999999"


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


def link_row(**over):
    base = dict(
        user_id=USER_ID, phone_e164=PHONE, wa_id="2348012345678",
        status=WhatsAppLinkStatus.ACTIVE.value, linked_at=datetime.now(timezone.utc),
        revoked_at=None, revoked_reason=None, deleted=False,
    )
    base.update(over)
    return SimpleNamespace(id="link-1", **base)


def _service(*, own_link=None, phone_holder=None, active_holder=None):
    svc = object.__new__(WhatsAppLinkService)
    svc._whatsapp_link_repo = MagicMock()
    svc._otp = MagicMock()
    svc._conversations = MagicMock()
    svc._handoff = MagicMock()
    svc._audit = MagicMock()

    repo = svc._whatsapp_link_repo
    repo.get_by_user_id = AsyncMock(return_value=own_link)
    repo.get_any_by_phone = AsyncMock(return_value=phone_holder)
    repo.get_active_by_phone = AsyncMock(return_value=active_holder)
    repo._session = MagicMock()

    async def _create(dto):
        return link_row(
            user_id=dto.user_id, phone_e164=dto.phone_e164, wa_id=dto.wa_id,
            status=dto.status.value, linked_at=None,
        )

    repo.create_return_model = AsyncMock(side_effect=_create)

    # The mutation helpers are synchronous and act on the attached row, so the fakes
    # apply the same field changes the real ones do — the tests assert on the row.
    def _claim(row, phone_e164, wa_id):
        row.phone_e164, row.wa_id = phone_e164, wa_id
        row.status, row.linked_at = WhatsAppLinkStatus.PENDING.value, None
        return row

    def _activate(row, at):
        row.status, row.linked_at = WhatsAppLinkStatus.ACTIVE.value, at
        return row

    def _release(row, reason, at):
        row.phone_e164, row.wa_id = None, None
        row.status, row.revoked_reason, row.revoked_at = (
            WhatsAppLinkStatus.REVOKED.value, reason, at
        )
        return row

    repo.claim_number = MagicMock(side_effect=_claim)
    repo.activate = MagicMock(side_effect=_activate)
    repo.release_number = MagicMock(side_effect=_release)

    svc._otp.send_otp = AsyncMock(return_value=600)
    svc._otp.verify_otp = AsyncMock(return_value=None)
    svc._conversations.set_whatsapp_thread_owner = AsyncMock(return_value=None)
    svc._audit.schedule = MagicMock()
    return svc


class TestResolution:
    """The one lookup every downstream flow trusts."""

    async def test_an_active_link_resolves_to_its_account(self):
        svc = _service(active_holder=link_row())
        assert await svc.resolve_user_for_phone(PHONE) == USER_ID

    async def test_an_unknown_number_resolves_to_nobody(self):
        svc = _service(active_holder=None)
        assert await svc.resolve_user_for_phone(PHONE) is None

    async def test_it_asks_only_for_active_links(self):
        # A pending attempt is not a link: someone who starts linking a number they do
        # not control must never become resolvable for it.
        svc = _service(active_holder=None)
        await svc.resolve_user_for_phone(PHONE)
        svc._whatsapp_link_repo.get_active_by_phone.assert_awaited_once_with(PHONE)

    async def test_it_normalizes_the_number_before_looking_it_up(self):
        # Meta hands us digits; the rest of the app keys on E.164. A missed conversion
        # here would silently make every linked number unresolvable.
        svc = _service(active_holder=link_row())
        assert await svc.resolve_user_for_phone("2348012345678") == USER_ID
        svc._whatsapp_link_repo.get_active_by_phone.assert_awaited_once_with(PHONE)


class TestStartLink:
    async def test_creates_a_pending_link_and_sends_the_code_over_whatsapp(self):
        svc = _service(own_link=None)
        challenge = await svc.start_link(USER_ID, PHONE)

        assert challenge.phone_e164 == PHONE
        assert challenge.resend_after_seconds == 600
        created = svc._whatsapp_link_repo.create_return_model.await_args.args[0]
        assert created.status == WhatsAppLinkStatus.PENDING

        channel, recipient = svc._otp.send_otp.await_args.args
        assert channel == OtpChannel.WHATSAPP
        assert recipient.international_number == PHONE

    async def test_refuses_a_number_another_account_already_holds(self):
        svc = _service(own_link=None, phone_holder=link_row(user_id=OTHER_USER_ID))
        with pytest.raises(ValidationException) as err:
            await svc.start_link(USER_ID, PHONE)
        assert NUMBER_UNAVAILABLE_MESSAGE in str(err.value)
        svc._otp.send_otp.assert_not_awaited()

    async def test_refuses_a_number_another_account_is_merely_attempting(self):
        # Checking only ACTIVE holders here would let two accounts race for one number
        # and leave the loser's confirmation failing on a constraint violation.
        pending_elsewhere = link_row(user_id=OTHER_USER_ID, status=WhatsAppLinkStatus.PENDING.value)
        svc = _service(own_link=None, phone_holder=pending_elsewhere)
        with pytest.raises(ValidationException):
            await svc.start_link(USER_ID, PHONE)

    async def test_refuses_a_number_that_is_not_a_number(self):
        svc = _service(own_link=None)
        with pytest.raises(ValidationException):
            await svc.start_link(USER_ID, "12345")
        svc._otp.send_otp.assert_not_awaited()

    async def test_a_repeat_attempt_on_the_same_number_reuses_the_row(self):
        existing = link_row(status=WhatsAppLinkStatus.PENDING.value, linked_at=None)
        svc = _service(own_link=existing, phone_holder=existing)
        await svc.start_link(USER_ID, PHONE)
        svc._whatsapp_link_repo.create_return_model.assert_not_awaited()
        assert existing.status == WhatsAppLinkStatus.PENDING.value


class TestNumberChange:
    """§7.4.4: a number change is a re-verification, and the old thread goes cold."""

    async def test_releases_the_old_number_before_starting_the_new_attempt(self):
        active = link_row()
        svc = _service(own_link=active, phone_holder=None)
        await svc.start_link(USER_ID, OTHER_PHONE)

        svc._whatsapp_link_repo.release_number.assert_called_once()
        assert active.phone_e164 == OTHER_PHONE
        assert active.status == WhatsAppLinkStatus.PENDING.value

    async def test_the_old_thread_stops_belonging_to_the_account(self):
        svc = _service(own_link=link_row(), phone_holder=None)
        await svc.start_link(USER_ID, OTHER_PHONE)
        # Detached first, so there is no window in which both numbers resolve.
        assert (PHONE, None) == svc._conversations.set_whatsapp_thread_owner.await_args_list[0].args

    async def test_the_new_number_is_not_live_until_its_code_is_confirmed(self):
        active = link_row()
        svc = _service(own_link=active, phone_holder=None)
        await svc.start_link(USER_ID, OTHER_PHONE)
        assert active.status != WhatsAppLinkStatus.ACTIVE.value


class TestConfirmLink:
    async def test_activates_the_link_and_adopts_the_existing_thread(self):
        pending = link_row(status=WhatsAppLinkStatus.PENDING.value, linked_at=None)
        svc = _service(own_link=pending)
        await svc.confirm_link(USER_ID, PHONE, "654123")

        assert pending.status == WhatsAppLinkStatus.ACTIVE.value
        # §7.8 — one conversation object per person, not one per surface.
        svc._conversations.set_whatsapp_thread_owner.assert_awaited_once_with(PHONE, USER_ID)

    async def test_verifies_the_code_on_the_whatsapp_channel(self):
        # Namespacing matters: a code sent over WhatsApp must not be spendable as the
        # signup SMS code for the same number.
        pending = link_row(status=WhatsAppLinkStatus.PENDING.value)
        svc = _service(own_link=pending)
        await svc.confirm_link(USER_ID, PHONE, "654123")
        channel, recipient, code = svc._otp.verify_otp.await_args.args
        assert channel == OtpChannel.WHATSAPP
        assert recipient.international_number == PHONE
        assert code == "654123"

    async def test_refuses_a_number_that_is_not_the_pending_one(self):
        # Otherwise a caller could confirm with a code for one number and be linked to
        # another they merely named in the request.
        svc = _service(own_link=link_row(phone_e164=PHONE))
        with pytest.raises(ResourceNotFoundException):
            await svc.confirm_link(USER_ID, OTHER_PHONE, "654123")
        svc._otp.verify_otp.assert_not_awaited()

    async def test_refuses_when_the_account_has_no_attempt_at_all(self):
        svc = _service(own_link=None)
        with pytest.raises(ResourceNotFoundException):
            await svc.confirm_link(USER_ID, PHONE, "654123")

    async def test_records_the_number_in_the_audit_trail(self):
        svc = _service(own_link=link_row(status=WhatsAppLinkStatus.PENDING.value))
        await svc.confirm_link(USER_ID, PHONE, "654123")
        action = svc._audit.schedule.call_args.args[0]
        assert action == AuditActionType.WHATSAPP_NUMBER_LINKED
        assert svc._audit.schedule.call_args.kwargs["details"]["phone_e164"] == PHONE


class TestUnlink:
    async def test_releases_the_number_so_another_account_can_claim_it(self):
        active = link_row()
        svc = _service(own_link=active)
        await svc.unlink(USER_ID)
        # A revoked row that kept its number would hold the unique constraint forever.
        assert active.phone_e164 is None
        assert active.status == WhatsAppLinkStatus.REVOKED.value

    async def test_the_thread_goes_cold(self):
        svc = _service(own_link=link_row())
        await svc.unlink(USER_ID)
        svc._conversations.set_whatsapp_thread_owner.assert_awaited_once_with(PHONE, None)

    async def test_the_released_number_is_still_traceable(self):
        # The row stops holding it, so the audit detail is the only remaining record.
        svc = _service(own_link=link_row())
        await svc.unlink(USER_ID)
        assert svc._audit.schedule.call_args.kwargs["details"]["phone_e164"] == PHONE

    async def test_unlinking_nothing_is_refused(self):
        svc = _service(own_link=None)
        with pytest.raises(ResourceNotFoundException):
            await svc.unlink(USER_ID)

    async def test_unlinking_twice_is_refused(self):
        svc = _service(own_link=link_row(status=WhatsAppLinkStatus.REVOKED.value, phone_e164=None))
        with pytest.raises(ResourceNotFoundException):
            await svc.unlink(USER_ID)


class TestWhatsAppToWebDirection:
    """§7.4.4: the number crosses in a signed token, never in the request body."""

    async def test_the_number_comes_from_the_token(self):
        svc = _service(own_link=None)
        svc._handoff.decode_link = AsyncMock(return_value=SimpleNamespace(
            phone=PHONE, intent=HandoffIntent.LINK, jti="n1",
        ))
        challenge = await svc.start_link_from_token(USER_ID, "signed-token")
        assert challenge.phone_e164 == PHONE
        _, recipient = svc._otp.send_otp.await_args.args
        assert recipient.international_number == PHONE

    async def test_starting_does_not_spend_the_bots_link(self):
        # A code can fail to arrive; a customer asking for a resend must not find the
        # page already dead.
        svc = _service(own_link=None)
        svc._handoff.decode_link = AsyncMock(return_value=SimpleNamespace(phone=PHONE))
        svc._handoff.redeem_link = AsyncMock()
        await svc.start_link_from_token(USER_ID, "signed-token")
        svc._handoff.redeem_link.assert_not_awaited()

    async def test_confirming_spends_the_bots_link_exactly_once(self):
        pending = link_row(status=WhatsAppLinkStatus.PENDING.value)
        svc = _service(own_link=pending)
        svc._handoff.redeem_link = AsyncMock(return_value=SimpleNamespace(phone=PHONE))
        await svc.confirm_link_from_token(USER_ID, "signed-token", "654123")
        svc._handoff.redeem_link.assert_awaited_once_with("signed-token")
        assert pending.status == WhatsAppLinkStatus.ACTIVE.value

    async def test_a_dead_token_links_nothing(self):
        svc = _service(own_link=link_row(status=WhatsAppLinkStatus.PENDING.value))
        svc._handoff.redeem_link = AsyncMock(side_effect=HandoffTokenError())
        with pytest.raises(HandoffTokenError):
            await svc.confirm_link_from_token(USER_ID, "replayed", "654123")
        svc._otp.verify_otp.assert_not_awaited()
