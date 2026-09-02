"""CaseDelegateService — §7.4.5's slim delegate (Decision O, D67/D77; WA-26).

This is access control, so the tests are mostly about what a delegate *cannot* reach and
who *cannot* create one. The four properties §7.4.5 names, each pinned here:

* one delegate per case, and a revoked one does not block a replacement;
* nothing is visible until the OTP is confirmed;
* only the account holder may authorize or revoke;
* revocation takes effect on the next event, which falls out of resolving the audience at
  send time rather than storing it.
"""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.verification.delegate.models import CaseDelegate
from main.app.domain.verification.delegate.service import (
    ALREADY_DELEGATED_MESSAGE,
    CaseDelegateService,
)
from main.appodus_utils import Utils
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import (
    ResourceNotFoundException,
    ValidationException,
)

CASE = "case-1"
OWNER = "cust-1"
STRANGER = "cust-2"
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
    token = db_session_ctx.set(session)
    yield session
    db_session_ctx.reset(token)


def _verification(customer_id=OWNER):
    return SimpleNamespace(
        id=CASE, vid="VP-2026-0042", customer_id=customer_id, status="IN_PROGRESS",
    )


def _service(rows=None, owner=OWNER):
    """The service over an in-memory delegate table.

    The repo's lifecycle mutators are the real ones — they hold the "keep the row, stamp
    the timestamp" rule, and mocking them would test the service against a rule that no
    longer had to be true.
    """
    from main.app.domain.verification.delegate.repo import CaseDelegateRepo

    svc = object.__new__(CaseDelegateService)
    held = {"rows": list(rows or [])}

    async def _live_for_case(verification_id):
        return next(
            (r for r in held["rows"]
             if r.verification_id == verification_id and r.revoked_at is None),
            None,
        )

    async def _active_for_case(verification_id):
        row = await _live_for_case(verification_id)
        return row if row is not None and row.verified_at is not None else None

    async def _active_by_phone(phone_e164):
        return next(
            (r for r in held["rows"]
             if r.phone_e164 == phone_e164 and r.verified_at is not None
             and r.revoked_at is None),
            None,
        )

    async def _create(dto):
        row = CaseDelegate(
            verification_id=dto.verification_id, name=dto.name, phone_e164=dto.phone_e164
        )
        held["rows"].append(row)
        return row

    repo = MagicMock(
        get_live_for_case=AsyncMock(side_effect=_live_for_case),
        get_active_for_case=AsyncMock(side_effect=_active_for_case),
        get_active_by_phone=AsyncMock(side_effect=_active_by_phone),
        create_return_model=AsyncMock(side_effect=_create),
        _session=MagicMock(),
    )
    repo.verify = lambda *a, **k: CaseDelegateRepo.verify(repo, *a, **k)
    repo.revoke = lambda *a, **k: CaseDelegateRepo.revoke(repo, *a, **k)

    async def _get_owned(verification_id, customer_id):
        if customer_id != owner:
            # Mirrors `VerificationService.get_owned`: another customer's case simply
            # does not exist as far as this caller is concerned.
            raise ResourceNotFoundException(resource="verification")
        return _verification(owner)

    svc._case_delegate_repo = repo
    svc._verification_service = MagicMock(get_owned=AsyncMock(side_effect=_get_owned))
    svc._verification_repo = MagicMock(
        get_model=AsyncMock(return_value=_verification(owner))
    )
    svc._otp = MagicMock(send_otp=AsyncMock(return_value=600), verify_otp=AsyncMock())
    svc._audit = MagicMock(schedule=MagicMock())
    svc._held = held
    return svc


def _verified_row(phone=PHONE, case=CASE, name="Tunde"):
    row = CaseDelegate(verification_id=case, name=name, phone_e164=phone)
    row.verified_at = Utils.datetime_now()
    return row


class TestAuthorization:
    async def test_the_owner_can_authorize_a_delegate(self):
        svc = _service()
        challenge = await svc.authorize(CASE, OWNER, "Tunde", PHONE)
        assert challenge.phone_e164 == PHONE
        svc._otp.send_otp.assert_awaited_once()

    async def test_a_stranger_cannot_authorize_on_someone_elses_case(self):
        """The buyer authorizes, and only the buyer. Ownership is proved against the case
        rather than taken from the request."""
        svc = _service()
        with pytest.raises(ResourceNotFoundException):
            await svc.authorize(CASE, STRANGER, "Tunde", PHONE)
        assert svc._held["rows"] == []

    async def test_only_one_live_delegate_per_case(self):
        svc = _service()
        await svc.authorize(CASE, OWNER, "Tunde", PHONE)
        with pytest.raises(ValidationException) as caught:
            await svc.authorize(CASE, OWNER, "Bola", "+2348090000000")
        assert ALREADY_DELEGATED_MESSAGE in str(caught.value.message)

    async def test_an_unconfirmed_authorization_still_holds_the_slot(self):
        """Two codes in flight to two numbers is worse than a clear refusal — the buyer
        would not know which one to relay."""
        svc = _service()
        await svc.authorize(CASE, OWNER, "Tunde", PHONE)
        assert svc._held["rows"][0].verified_at is None
        with pytest.raises(ValidationException):
            await svc.authorize(CASE, OWNER, "Bola", "+2348090000000")

    async def test_a_replacement_is_allowed_after_a_revocation(self):
        """A plain unique constraint would make the first revocation permanent."""
        svc = _service()
        await svc.authorize(CASE, OWNER, "Tunde", PHONE)
        await svc.confirm(CASE, OWNER, "654123")
        await svc.revoke(CASE, OWNER)
        challenge = await svc.authorize(CASE, OWNER, "Bola", "+2348090000000")
        assert challenge.phone_e164 == "+2348090000000"

    async def test_a_malformed_number_is_refused_before_a_code_is_sent(self):
        svc = _service()
        with pytest.raises(ValidationException):
            await svc.authorize(CASE, OWNER, "Tunde", "+234")
        svc._otp.send_otp.assert_not_called()

    async def test_a_nameless_delegate_is_refused(self):
        """The bot addresses them by name, and "Hi  — you're receiving updates" is not
        a message anyone should receive."""
        svc = _service()
        with pytest.raises(ValidationException):
            await svc.authorize(CASE, OWNER, "   ", PHONE)


class TestVerification:
    async def test_confirming_starts_visibility(self):
        svc = _service()
        await svc.authorize(CASE, OWNER, "Tunde", PHONE)
        result = await svc.confirm(CASE, OWNER, "654123")
        assert result.verified is True
        assert await svc.resolve_delegate_for_phone(PHONE) is not None

    async def test_an_unverified_delegate_resolves_to_nothing(self):
        """Someone nominated but never confirmed has no more standing than a stranger."""
        svc = _service()
        await svc.authorize(CASE, OWNER, "Tunde", PHONE)
        assert await svc.resolve_delegate_for_phone(PHONE) is None

    async def test_a_stranger_cannot_confirm(self):
        svc = _service()
        await svc.authorize(CASE, OWNER, "Tunde", PHONE)
        with pytest.raises(ResourceNotFoundException):
            await svc.confirm(CASE, STRANGER, "654123")

    async def test_confirming_with_no_authorization_is_not_found(self):
        svc = _service()
        with pytest.raises(ResourceNotFoundException):
            await svc.confirm(CASE, OWNER, "654123")


class TestRevocation:
    async def test_revocation_is_effective_immediately_on_the_next_lookup(self):
        """§7.4.5's "takes effect on the next event": the audience is resolved at send
        time, so there is nothing to sweep and no window to get wrong."""
        svc = _service([_verified_row()])
        assert await svc.resolve_delegate_for_phone(PHONE) is not None
        await svc.revoke(CASE, OWNER)
        assert await svc.resolve_delegate_for_phone(PHONE) is None

    async def test_a_stranger_cannot_revoke(self):
        svc = _service([_verified_row()])
        with pytest.raises(ResourceNotFoundException):
            await svc.revoke(CASE, STRANGER)
        assert await svc.resolve_delegate_for_phone(PHONE) is not None

    async def test_the_revoked_row_is_kept(self):
        """"Who could see this, and until when" is the question a disputed verification
        eventually asks."""
        svc = _service([_verified_row()])
        await svc.revoke(CASE, OWNER)
        row = svc._held["rows"][0]
        assert row.revoked_at is not None
        assert row.verified_at is not None

    async def test_revoking_nothing_is_not_found(self):
        svc = _service()
        with pytest.raises(ResourceNotFoundException):
            await svc.revoke(CASE, OWNER)


class TestStopFromADelegate:
    """D77 — a delegate has no consent row, so STOP ends the delegation itself."""

    async def test_stop_revokes_the_delegation(self):
        svc = _service([_verified_row()])
        revoked = await svc.revoke_by_phone(PHONE)
        assert revoked is not None
        assert await svc.resolve_delegate_for_phone(PHONE) is None

    async def test_the_account_holder_is_told(self, monkeypatch):
        """The useful response is to authorize somebody else, which the buyer cannot do
        if they only find out by opening the case page."""
        import main.app.domain.verification.delegate.service as delegate_mod
        from main.app.core.events.events import EventType

        published = []
        monkeypatch.setattr(
            delegate_mod, "publish_domain_event",
            AsyncMock(side_effect=lambda e: published.append(e)),
        )
        svc = _service([_verified_row()])
        await svc.revoke_by_phone(PHONE)

        revoked = [e for e in published if e.type == EventType.DELEGATE_REVOKED]
        assert revoked and revoked[0].recipient_user_ids == (OWNER,)
        assert revoked[0].data["name"] == "Tunde"

    async def test_stop_from_a_number_that_holds_no_delegation_does_nothing(self):
        svc = _service()
        assert await svc.revoke_by_phone("+2349999999999") is None


class TestMilestoneAudience:
    async def test_a_verified_delegate_receives_the_delegate_template(self, monkeypatch):
        """Always `delegate_status`, never the customer's template — which is what makes
        "never documents, reports, chat history or intake data" structural: that template
        has no link parameter for a report to travel in."""
        from kink import di
        from main.app.domain.channel.whatsapp.milestones import WhatsAppMilestoneSender

        sender = MagicMock(send_delegate_milestone=AsyncMock())
        monkeypatch.setitem(di._services, WhatsAppMilestoneSender, sender)
        monkeypatch.setitem(di._memoized_services, WhatsAppMilestoneSender, sender)

        svc = _service([_verified_row()])
        await svc.notify_milestone(CASE)

        sender.send_delegate_milestone.assert_awaited_once()
        args, kwargs = sender.send_delegate_milestone.await_args
        assert args[0] == PHONE and args[1] == "VP-2026-0042"
        assert kwargs["delegate_name"] == "Tunde"

    async def test_a_revoked_delegate_receives_nothing(self, monkeypatch):
        from kink import di
        from main.app.domain.channel.whatsapp.milestones import WhatsAppMilestoneSender

        sender = MagicMock(send_delegate_milestone=AsyncMock())
        monkeypatch.setitem(di._services, WhatsAppMilestoneSender, sender)
        monkeypatch.setitem(di._memoized_services, WhatsAppMilestoneSender, sender)

        svc = _service([_verified_row()])
        await svc.revoke(CASE, OWNER)
        await svc.notify_milestone(CASE)

        sender.send_delegate_milestone.assert_not_called()

    async def test_a_case_with_no_delegate_is_a_no_op(self):
        svc = _service()
        await svc.notify_milestone(CASE)  # no exception, nothing resolved


class TestListing:
    async def test_the_owner_sees_their_delegate(self):
        svc = _service([_verified_row()])
        listed = await svc.list_for_case(CASE, OWNER)
        assert len(listed) == 1 and listed[0].name == "Tunde"

    async def test_a_stranger_sees_nothing_because_the_case_is_not_theirs(self):
        svc = _service([_verified_row()])
        with pytest.raises(ResourceNotFoundException):
            await svc.list_for_case(CASE, STRANGER)
