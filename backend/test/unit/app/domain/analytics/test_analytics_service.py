"""AnalyticsService (§18.1, D38) — pure aggregation over mocked repo pulls."""
from contextlib import asynccontextmanager
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from main.app.core.state.status import VerificationStatus, VerificationTier
from main.app.domain.analytics.service import AnalyticsService
from main.appodus_utils import Utils
from main.appodus_utils.db.session import db_session_ctx

V1, V2, V3 = UUID(int=1), UUID(int=2), UUID(int=3)


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


def _row(vid, tier, status, paid=True, state="Lagos", days=3):
    now = Utils.datetime_now()
    return {
        "id": vid, "tier": tier.value if tier else None, "status": status.value,
        "paid_at": now - timedelta(days=days) if paid else None,
        "updated": now, "state": state,
    }


def _make_service():
    svc = object.__new__(AnalyticsService)
    svc._verifications = AsyncMock()
    svc._payments = AsyncMock()
    svc._tasks = AsyncMock()
    svc._reports = AsyncMock()
    svc._config = AsyncMock()
    svc._config.get_int = AsyncMock(return_value=6)  # ANALYTICS_TREND_MONTHS default
    svc._channel_events = AsyncMock()
    svc._whatsapp_links = AsyncMock()
    svc._whatsapp_consents = AsyncMock()
    svc._whatsapp_inbound = AsyncMock()
    svc._whatsapp_number_health = AsyncMock()
    return svc


class TestFunnel:
    async def test_counts_each_stage(self):
        svc = _make_service()
        svc._verifications.analytics_snapshot = AsyncMock(return_value=[
            _row(V1, VerificationTier.BASIC, VerificationStatus.COMPLETED),
            _row(V2, VerificationTier.STANDARD, VerificationStatus.PAID),
            _row(V3, None, VerificationStatus.DRAFT, paid=False),
        ])
        funnel = await svc.funnel()
        assert funnel.created == 3
        assert funnel.submitted == 2   # not DRAFT
        assert funnel.paid == 2
        assert funnel.completed == 1
        assert 0.0 < funnel.completion_rate <= 1.0


class TestTimeByTier:
    async def test_avg_days_for_completed(self):
        svc = _make_service()
        svc._verifications.analytics_snapshot = AsyncMock(return_value=[
            _row(V1, VerificationTier.BASIC, VerificationStatus.COMPLETED, days=4),
        ])
        rows = await svc.time_by_tier()
        basic = next(r for r in rows if r.tier == VerificationTier.BASIC)
        assert basic.completed_count == 1
        assert 3.5 <= basic.avg_days <= 4.5


class TestRevenue:
    async def test_revenue_by_tier_and_location(self):
        svc = _make_service()
        svc._verifications.analytics_snapshot = AsyncMock(return_value=[
            _row(V1, VerificationTier.PREMIUM, VerificationStatus.COMPLETED, state="Lagos"),
            _row(V2, VerificationTier.BASIC, VerificationStatus.PAID, state="Abuja"),
        ])
        svc._payments.revenue_by_verification = AsyncMock(return_value={
            Utils.uuid_to_hex(V1): 30_000_000, Utils.uuid_to_hex(V2): 5_000_000,
        })
        rev = await svc.revenue()
        assert rev.total_minor == 35_000_000
        premium = next(t for t in rev.by_tier if t.tier == VerificationTier.PREMIUM)
        assert premium.revenue_minor == 30_000_000
        assert rev.by_location[0].revenue_minor == 30_000_000  # sorted desc


class TestRegional:
    async def test_regional_rolls_up_by_state(self):
        svc = _make_service()
        svc._verifications.analytics_snapshot = AsyncMock(return_value=[
            _row(V1, VerificationTier.BASIC, VerificationStatus.IN_PROGRESS, state="Lagos"),
            _row(V2, VerificationTier.BASIC, VerificationStatus.COMPLETED, state="Lagos"),
        ])
        svc._payments.revenue_by_verification = AsyncMock(return_value={Utils.uuid_to_hex(V2): 5_000_000})
        svc._reports.list_released_scores = AsyncMock(return_value={Utils.uuid_to_hex(V2): 90})
        rows = await svc.regional()
        lagos = next(r for r in rows if r.state == "Lagos")
        assert lagos.active == 1 and lagos.completed == 1
        assert lagos.revenue_minor == 5_000_000
        assert lagos.avg_trust_score == 90.0


class TestAgentTrends:
    async def test_groups_by_month(self):
        svc = _make_service()
        now = Utils.datetime_now()
        svc._tasks.list_approved_since = AsyncMock(return_value=[(now, 100), (now, 80)])
        trends = await svc.agent_trends()
        assert len(trends.points) == 1
        assert trends.points[0].completed_tasks == 2
        assert trends.points[0].avg_quality == 90.0


# ─── WhatsApp channel (§7.10, WA-43) ──────────────────────────────
#
# Seven metrics, four of them rates. The tests below are mostly about denominators: §7.10's
# headline number is a ratio, and every way of getting a ratio wrong is a way of reporting
# that the channel is working when it is not.

from main.app.domain.channel.whatsapp.analytics.models import (  # noqa: E402
    WhatsAppChannelEventType,
    WhatsAppQualityRating,
)
from main.app.domain.channel.whatsapp.consent.models import WhatsAppConsentKind  # noqa: E402


def _channel_service(counts=None, page_codes=None, reasons=None, **overrides):
    svc = _make_service()
    svc._config.get_int = AsyncMock(return_value=30)  # CHANNEL_ANALYTICS_WINDOW_DAYS
    base = {event_type.value: 0 for event_type in WhatsAppChannelEventType}
    base.update(counts or {})
    svc._channel_events.count_by_type = AsyncMock(return_value=base)
    svc._channel_events.count_by_page_code = AsyncMock(return_value=page_codes or {})
    svc._channel_events.count_by_escalation_reason = AsyncMock(return_value=reasons or {})
    svc._whatsapp_links.count_active = AsyncMock(return_value=overrides.get("linked", 0))
    svc._whatsapp_consents.count_granted = AsyncMock(
        return_value={
            WhatsAppConsentKind.UTILITY.value: overrides.get("utility", 0),
            WhatsAppConsentKind.MARKETING.value: overrides.get("marketing", 0),
        }
    )
    svc._whatsapp_inbound.count_by_kind = AsyncMock(return_value=overrides.get("audio", 0))
    svc._whatsapp_number_health.current = AsyncMock(return_value=overrides.get("health"))
    return svc


class TestSeamConversion:
    async def test_the_headline_rate_is_payments_over_completed_intakes(self):
        svc = _channel_service(counts={
            WhatsAppChannelEventType.INTAKE_COMPLETED.value: 10,
            WhatsAppChannelEventType.PAYMENT_COMPLETED.value: 3,
        })

        result = await svc.whatsapp_channel(None)

        assert result.intake_completed == 10
        assert result.payment_completed == 3
        assert result.seam_conversion_rate == 0.3

    async def test_no_intakes_yet_reports_zero_rather_than_dividing_by_zero(self):
        # The state of the channel on day one, and on any quiet window since.
        svc = _channel_service()

        result = await svc.whatsapp_channel(None)

        assert result.seam_conversion_rate == 0.0


class TestDemandAndFlow:
    async def test_enquiries_are_broken_down_by_page_code_biggest_first(self):
        svc = _channel_service(
            counts={WhatsAppChannelEventType.ENQUIRY.value: 9},
            page_codes={"web-home": 2, "web-pricing": 6, "direct": 1},
        )

        result = await svc.whatsapp_channel(None)

        assert result.enquiries == 9
        assert [row.label for row in result.enquiries_by_page_code] == [
            "web-pricing", "web-home", "direct",
        ]

    async def test_enquiry_to_intake_uses_enquiries_as_the_denominator(self):
        svc = _channel_service(counts={
            WhatsAppChannelEventType.ENQUIRY.value: 8,
            WhatsAppChannelEventType.INTAKE_STARTED.value: 2,
        })

        result = await svc.whatsapp_channel(None)

        assert result.enquiry_to_intake_rate == 0.25


class TestEscalation:
    async def test_the_rate_and_the_reasons_are_both_reported(self):
        # §7.10 asks for both: a channel escalating on guardrail topics is working as
        # designed, while one escalating on unmatched intents names the flow to build.
        svc = _channel_service(
            counts={
                WhatsAppChannelEventType.ENQUIRY.value: 10,
                WhatsAppChannelEventType.ESCALATED.value: 4,
            },
            reasons={"GUARDRAIL_TOPIC": 3, "VOICE_NOTE": 1},
        )

        result = await svc.whatsapp_channel(None)

        assert result.escalation_rate == 0.4
        assert result.escalations_by_reason[0].label == "GUARDRAIL_TOPIC"
        assert result.escalations_by_reason[0].count == 3


class TestOptInRates:
    async def test_the_denominator_is_reachable_numbers_not_consent_rows(self):
        """D84 — of the customers this channel can actually reach, how many said yes."""
        svc = _channel_service(linked=8, utility=6, marketing=2)

        result = await svc.whatsapp_channel(None)

        assert result.linked_numbers == 8
        assert result.utility_opt_in_rate == 0.75
        assert result.marketing_opt_in_rate == 0.25

    async def test_nobody_linked_yet_reports_zero(self):
        svc = _channel_service(linked=0, utility=0, marketing=0)

        result = await svc.whatsapp_channel(None)

        assert result.utility_opt_in_rate == 0.0


class TestPlatformSignals:
    async def test_a_never_synced_number_reports_no_health_rather_than_green(self):
        svc = _channel_service(health=None)

        result = await svc.whatsapp_channel(None)

        assert result.number_health is None

    async def test_a_synced_rating_is_reported_with_its_age_and_any_error(self):
        health = MagicMock()
        health.quality_rating = WhatsAppQualityRating.YELLOW.value
        health.messaging_limit_tier = "TIER_1K"
        health.last_synced_at = Utils.datetime_now()
        health.sync_error = None
        svc = _channel_service(health=health)

        result = await svc.whatsapp_channel(None)

        assert result.number_health.quality_rating == "YELLOW"
        assert result.number_health.synced_at is not None

    async def test_voice_note_volume_is_counted_off_the_inbound_journal(self):
        # Not off the escalation reason: a voice note arriving on a thread already in
        # HUMAN mode never reaches the bot, and §7.10 wants how many arrived.
        svc = _channel_service(audio=7)

        result = await svc.whatsapp_channel(None)

        assert result.voice_notes == 7


class TestWindow:
    async def test_an_explicit_window_overrides_the_configured_default(self):
        svc = _channel_service()

        result = await svc.whatsapp_channel(7)

        assert result.window_days == 7
        svc._config.get_int.assert_not_awaited()

    async def test_no_window_falls_back_to_the_configured_default(self):
        svc = _channel_service()

        result = await svc.whatsapp_channel(None)

        assert result.window_days == 30
