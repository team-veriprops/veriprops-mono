"""The §7.10 fact recorder (WA-43, D80).

The recorder is sprinkled through the conversation path, so its single most important
property is the one that is easiest to regress: **it never raises**. A metric write that
could fail a turn would trade the channel's reliability for a number on a dashboard.

The second property is that seam conversion stays honest. `PAYMENT_CONFIRMED` fires for
every payment on the platform; counting all of them against a WhatsApp intake denominator
would report a conversion rate well above 100%.
"""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.channel.whatsapp.analytics.models import WhatsAppChannelEventType
from main.app.domain.channel.whatsapp.analytics.recorder import ChannelEventRecorder
from main.app.domain.channel.whatsapp.bot.session.models import EscalationReason
from main.appodus_utils.db.session import db_session_ctx


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


def _recorder(**repo_overrides):
    recorder = object.__new__(ChannelEventRecorder)
    repo = MagicMock()
    repo.create = AsyncMock()
    repo.has_events_for_verification = AsyncMock(return_value=True)
    for name, value in repo_overrides.items():
        setattr(repo, name, value)
    recorder._events = repo
    return recorder, repo


class TestItNeverRaises:
    async def test_a_failing_write_is_swallowed(self):
        # The turn it describes already happened — the customer was answered, the link
        # was minted. Raising here would undo that for the sake of a count.
        recorder, _repo = _recorder(create=AsyncMock(side_effect=RuntimeError("db gone")))

        await recorder.record(WhatsAppChannelEventType.ENQUIRY, phone_e164="+2348012345678")

    async def test_a_failing_origin_check_does_not_fail_a_confirmed_payment(self):
        recorder, repo = _recorder(
            has_events_for_verification=AsyncMock(side_effect=RuntimeError("db gone"))
        )

        await recorder.record_payment_if_channel_case("vid-1", "cust-1")

        repo.create.assert_not_awaited()


class TestWhatGetsWritten:
    async def test_an_escalation_records_its_reason(self):
        recorder, repo = _recorder()

        await recorder.record(
            WhatsAppChannelEventType.ESCALATED,
            phone_e164="+2348012345678",
            reason=EscalationReason.VOICE_NOTE,
        )

        written = repo.create.await_args.args[0]
        assert written.event_type == WhatsAppChannelEventType.ESCALATED.value
        assert written.reason == EscalationReason.VOICE_NOTE.value
        assert written.occurred_at is not None

    async def test_an_enquiry_carries_its_page_code(self):
        recorder, repo = _recorder()

        await recorder.record(
            WhatsAppChannelEventType.ENQUIRY,
            phone_e164="+2348012345678",
            page_code="web-pricing",
        )

        assert repo.create.await_args.args[0].page_code == "web-pricing"


class TestSeamConversionStaysHonest:
    async def test_a_channel_case_is_counted(self):
        recorder, repo = _recorder()

        await recorder.record_payment_if_channel_case("vid-1", "cust-1")

        written = repo.create.await_args.args[0]
        assert written.event_type == WhatsAppChannelEventType.PAYMENT_COMPLETED.value
        assert written.verification_id == "vid-1"

    async def test_an_ordinary_web_payment_is_counted_into_nothing(self):
        # Without this the seam conversion rate would be every payment on the platform
        # divided by the handful that came through chat.
        recorder, repo = _recorder(
            has_events_for_verification=AsyncMock(return_value=False)
        )

        await recorder.record_payment_if_channel_case("vid-web", "cust-1")

        repo.create.assert_not_awaited()
