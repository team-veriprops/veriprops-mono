"""WhatsAppConsentService — the §26.4.6 opt-in ledger (D63/D64, WA-27).

The property under test is that consent is a *history*, not a flag. Granted-ness is derived
from a grant/revoke pair, so what these tests pin is that the derivation stays right across
the sequences a real customer produces — tick, untick, STOP, START, tick again — and that
each transition records who asked.

The D64 asymmetry gets its own class because it is the one thing here a reader would
otherwise assume is a bug: START restores utility and deliberately leaves marketing off.
"""
from contextlib import asynccontextmanager
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.channel.whatsapp.consent.models import (
    WhatsAppConsent,
    WhatsAppConsentKind,
    WhatsAppConsentSource,
    consent_granted,
)
from main.app.domain.channel.whatsapp.consent.repo import WhatsAppConsentRepo
from main.app.domain.channel.whatsapp.consent.service import WhatsAppConsentService
from main.appodus_utils import Utils
from main.appodus_utils.db.session import db_session_ctx

USER = "user-1"


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


def _row() -> WhatsAppConsent:
    """A bare consent row — every timestamp null, which is "consented to nothing"."""
    return WhatsAppConsent(user_id=USER)


def _service(row=None):
    """The service over a repo that holds one in-memory row.

    `apply` is the real repo method rather than a mock: it is where the "stamp only the
    side that moved" rule lives, and mocking it would test the service against a rule that
    no longer had to hold.
    """
    svc = object.__new__(WhatsAppConsentService)
    held = {"row": row}

    async def _get_by_user_id(user_id):
        return held["row"]

    async def _create(dto):
        held["row"] = WhatsAppConsent(user_id=dto.user_id)
        return held["row"]

    repo = MagicMock(
        get_by_user_id=AsyncMock(side_effect=_get_by_user_id),
        create_return_model=AsyncMock(side_effect=_create),
        _session=MagicMock(),
    )
    repo.apply = lambda *args, **kwargs: WhatsAppConsentRepo.apply(repo, *args, **kwargs)
    svc._whatsapp_consent_repo = repo
    svc._audit = MagicMock(schedule=MagicMock())
    svc._held = held
    return svc


class TestDerivedGrantedness:
    def test_never_asked_is_not_consent(self):
        assert consent_granted(None, None) is False

    def test_a_grant_with_no_revocation_holds(self):
        assert consent_granted(Utils.datetime_now(), None) is True

    def test_a_later_revocation_wins(self):
        granted = Utils.datetime_now()
        assert consent_granted(granted, granted + timedelta(seconds=1)) is False

    def test_a_later_grant_beats_an_earlier_revocation(self):
        """Re-consenting must work without erasing the revocation that preceded it —
        §26.8 wants the history kept, so the newer stamp has to be what decides."""
        revoked = Utils.datetime_now()
        assert consent_granted(revoked + timedelta(seconds=1), revoked) is True

    def test_a_revocation_alone_is_not_consent(self):
        assert consent_granted(None, Utils.datetime_now()) is False


class TestCapture:
    async def test_absent_row_reads_as_both_unticked(self):
        """§26.4.6's controls are unticked by default, and silence is never consent."""
        svc = _service()
        described = await svc.describe(USER)
        assert (described.utility, described.marketing) == (False, False)

    async def test_setting_both_opens_a_row_and_grants_both(self):
        svc = _service()
        result = await svc.set_consents(
            USER, True, True, WhatsAppConsentSource.PAY_SCREEN
        )
        assert (result.utility, result.marketing) == (True, True)
        assert await svc.utility_granted(USER) is True
        assert await svc.marketing_granted(USER) is True

    async def test_unticking_one_leaves_the_other(self):
        svc = _service(_row())
        await svc.set_consents(USER, True, True, WhatsAppConsentSource.PAY_SCREEN)
        await svc.set_consents(USER, True, False, WhatsAppConsentSource.ACCOUNT_SETTINGS)
        assert await svc.utility_granted(USER) is True
        assert await svc.marketing_granted(USER) is False

    async def test_the_capture_point_is_recorded(self):
        """"Who turned this off?" is answerable only at the moment it happens, so the
        source is stored rather than inferred later."""
        svc = _service(_row())
        await svc.set_consents(USER, True, False, WhatsAppConsentSource.WA_PAY_LANDING)
        row = svc._held["row"]
        assert row.utility_source == WhatsAppConsentSource.WA_PAY_LANDING.value
        assert row.marketing_source == WhatsAppConsentSource.WA_PAY_LANDING.value

    async def test_a_change_is_audited_with_both_consents(self):
        svc = _service(_row())
        await svc.set_consents(USER, True, False, WhatsAppConsentSource.PAY_SCREEN)
        details = svc._audit.schedule.call_args.kwargs["details"]
        assert details == {
            "utility": True, "marketing": False,
            "source": WhatsAppConsentSource.PAY_SCREEN.value,
        }


class TestStopAndStart:
    async def test_stop_revokes_both(self):
        """D64: the customer said "stop", not "stop some"."""
        svc = _service(_row())
        await svc.set_consents(USER, True, True, WhatsAppConsentSource.PAY_SCREEN)
        await svc.revoke_all(USER, WhatsAppConsentSource.STOP_KEYWORD)
        assert await svc.utility_granted(USER) is False
        assert await svc.marketing_granted(USER) is False

    async def test_start_restores_utility_only(self):
        """The D64 asymmetry: marketing re-consent is a deliberate evidenced act on the
        web, not a one-word chat message."""
        svc = _service(_row())
        await svc.set_consents(USER, True, True, WhatsAppConsentSource.PAY_SCREEN)
        await svc.revoke_all(USER, WhatsAppConsentSource.STOP_KEYWORD)
        await svc.grant_utility(USER, WhatsAppConsentSource.START_KEYWORD)
        assert await svc.utility_granted(USER) is True
        assert await svc.marketing_granted(USER) is False

    async def test_stop_from_a_customer_who_never_opted_in_is_still_recorded(self):
        """A STOP is evidence in its own right — it is what makes a later send a mistake
        we can see, rather than one we have to reason about."""
        svc = _service()
        await svc.revoke_all(USER, WhatsAppConsentSource.STOP_KEYWORD)
        row = svc._held["row"]
        assert row is not None
        assert row.utility_revoked_at is not None
        assert row.utility_source == WhatsAppConsentSource.STOP_KEYWORD.value

    async def test_revocation_keeps_the_grant_that_preceded_it(self):
        """The pair of stamps is the §26.8 record: clearing the grant would lose the fact
        that consent was ever given, which is the half a regulator asks about."""
        svc = _service(_row())
        await svc.set_consents(USER, True, True, WhatsAppConsentSource.PAY_SCREEN)
        await svc.revoke_all(USER, WhatsAppConsentSource.STOP_KEYWORD)
        row = svc._held["row"]
        assert row.utility_granted_at is not None
        assert row.utility_revoked_at is not None


class TestRepoStamping:
    def test_apply_touches_only_the_side_that_moved(self):
        repo = MagicMock(_session=MagicMock())
        row = _row()
        now = Utils.datetime_now()
        WhatsAppConsentRepo.apply(
            repo, row, WhatsAppConsentKind.UTILITY, True,
            WhatsAppConsentSource.PAY_SCREEN, now,
        )
        assert row.utility_granted_at == now
        assert row.utility_revoked_at is None
        # The other consent is untouched — they share a row, not a state.
        assert row.marketing_granted_at is None

    def test_described_timestamp_is_the_newer_of_the_two(self):
        """A grant followed by a revoke has both stamps; showing the grant date beside
        "off" would read as a contradiction on the settings page."""
        row = _row()
        granted = Utils.datetime_now()
        row.utility_granted_at = granted
        row.utility_revoked_at = granted + timedelta(minutes=5)
        described = WhatsAppConsentService._to_dto(row)
        assert described.utility is False
        assert described.utility_updated_at == row.utility_revoked_at


class TestModelProperties:
    def test_the_orm_row_derives_both_consents(self):
        row = SimpleNamespace(
            utility_granted_at=Utils.datetime_now(), utility_revoked_at=None,
            marketing_granted_at=None, marketing_revoked_at=None,
        )
        assert WhatsAppConsent.utility.fget(row) is True
        assert WhatsAppConsent.marketing.fget(row) is False
