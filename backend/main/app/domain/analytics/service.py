"""Analytics service (PRD §18.1, D38).

Pure aggregation over the operational tables — no analytics entity, nothing stored.
Computes the conversion funnel, average verification time by tier, revenue by tier &
location, per-state regional performance, and the 6-month agent-performance trend.
Aggregation happens in Python over targeted repo pulls: fine at MVP volume; materialise
or cache if the dataset grows (consistent with the reputation-metrics posture, D32).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Dict, List, Optional

from kink import inject

from main.app.core.state.status import VerificationStatus, VerificationTier
from main.app.domain.analytics.models import (
    AgentTrendPointDto,
    AgentTrendsDto,
    ChannelCountDto,
    FunnelDto,
    LocationRevenueDto,
    RegionalRowDto,
    RevenueDto,
    TierRevenueDto,
    TierTimeDto,
    WhatsAppChannelAnalyticsDto,
    WhatsAppNumberHealthDto,
)
from main.app.domain.channel.whatsapp.analytics.health_service import (
    WhatsAppNumberHealthService,
)
from main.app.domain.channel.whatsapp.analytics.models import WhatsAppChannelEventType
from main.app.domain.channel.whatsapp.analytics.repo import WhatsAppChannelEventRepo
from main.app.domain.channel.whatsapp.consent.models import WhatsAppConsentKind
from main.app.domain.channel.whatsapp.consent.repo import WhatsAppConsentRepo
from main.app.domain.channel.whatsapp.inbound.repo import WhatsAppInboundMessageRepo
from main.app.domain.channel.whatsapp.link.repo import WhatsAppLinkRepo
from main.app.domain.payment.repo import PaymentRepo
from main.app.domain.verification.report.repo import ReportRepo
from main.app.domain.system_config.models import ConfigKey
from main.app.domain.system_config.service import ConfigService
from main.app.domain.verification.repo import VerificationRepo
from main.app.domain.verification.task.repo import VerificationTaskRepo
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.integrations.messaging.providers.whatsapp.inbound import InboundKind

_COMPLETED = VerificationStatus.COMPLETED.value
_PAID_STATES = {
    VerificationStatus.PAID.value, VerificationStatus.IN_PROGRESS.value,
    VerificationStatus.UNDER_REVIEW.value, VerificationStatus.COMPLETED.value,
    VerificationStatus.DISPUTED.value, VerificationStatus.REFUNDED.value,
}
_ACTIVE_STATES = {
    VerificationStatus.PAID.value, VerificationStatus.IN_PROGRESS.value,
    VerificationStatus.UNDER_REVIEW.value,
}
_UNKNOWN_STATE = "Unknown"


def _rate(num: int, denom: int) -> float:
    return round(num / denom, 4) if denom else 0.0


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class AnalyticsService:
    def __init__(
        self,
        verification_repo: VerificationRepo,
        payment_repo: PaymentRepo,
        task_repo: VerificationTaskRepo,
        report_repo: ReportRepo,
        config_service: ConfigService,
        whatsapp_channel_event_repo: WhatsAppChannelEventRepo,
        whatsapp_link_repo: WhatsAppLinkRepo,
        whatsapp_consent_repo: WhatsAppConsentRepo,
        whatsapp_inbound_message_repo: WhatsAppInboundMessageRepo,
        whatsapp_number_health_service: WhatsAppNumberHealthService,
    ):
        self._verifications = verification_repo
        self._payments = payment_repo
        self._tasks = task_repo
        self._reports = report_repo
        self._config = config_service
        self._channel_events = whatsapp_channel_event_repo
        self._whatsapp_links = whatsapp_link_repo
        self._whatsapp_consents = whatsapp_consent_repo
        self._whatsapp_inbound = whatsapp_inbound_message_repo
        self._whatsapp_number_health = whatsapp_number_health_service

    async def funnel(self) -> FunnelDto:
        rows = await self._verifications.analytics_snapshot()
        created = len(rows)
        submitted = sum(1 for r in rows if r["status"] != VerificationStatus.DRAFT.value)
        paid = sum(1 for r in rows if r["paid_at"] is not None)
        completed = sum(1 for r in rows if r["status"] == _COMPLETED)
        return FunnelDto(
            created=created, submitted=submitted, paid=paid, completed=completed,
            submit_rate=_rate(submitted, created),
            payment_rate=_rate(paid, submitted),
            completion_rate=_rate(completed, paid),
        )

    async def time_by_tier(self) -> List[TierTimeDto]:
        rows = await self._verifications.analytics_snapshot()
        totals: Dict[str, float] = defaultdict(float)
        counts: Dict[str, int] = defaultdict(int)
        for r in rows:
            if r["status"] == _COMPLETED and r["paid_at"] and r["updated"] and r["tier"]:
                days = max(0.0, (r["updated"] - r["paid_at"]).total_seconds() / 86400)
                totals[r["tier"]] += days
                counts[r["tier"]] += 1
        return [
            TierTimeDto(
                tier=tier,
                avg_days=round(totals[tier.value] / counts[tier.value], 2) if counts[tier.value] else 0.0,
                completed_count=counts[tier.value],
            )
            for tier in VerificationTier
        ]

    async def revenue(self) -> RevenueDto:
        rows = await self._verifications.analytics_snapshot()
        revenue_by_v = await self._payments.revenue_by_verification()
        by_tier_amt: Dict[str, int] = defaultdict(int)
        by_tier_cnt: Dict[str, int] = defaultdict(int)
        by_state_amt: Dict[str, int] = defaultdict(int)
        by_state_cnt: Dict[str, int] = defaultdict(int)
        total = 0
        for r in rows:
            rev = revenue_by_v.get(Utils.uuid_to_hex(r["id"]), 0)
            if rev <= 0:
                continue
            total += rev
            if r["tier"]:
                by_tier_amt[r["tier"]] += rev
                by_tier_cnt[r["tier"]] += 1
            state = r["state"] or _UNKNOWN_STATE
            by_state_amt[state] += rev
            by_state_cnt[state] += 1
        by_tier = [
            TierRevenueDto(tier=tier, revenue_minor=by_tier_amt[tier.value], count=by_tier_cnt[tier.value])
            for tier in VerificationTier
        ]
        by_location = [
            LocationRevenueDto(state=state, revenue_minor=amt, count=by_state_cnt[state])
            for state, amt in sorted(by_state_amt.items(), key=lambda kv: kv[1], reverse=True)
        ]
        return RevenueDto(total_minor=total, by_tier=by_tier, by_location=by_location)

    async def regional(self) -> List[RegionalRowDto]:
        rows = await self._verifications.analytics_snapshot()
        revenue_by_v = await self._payments.revenue_by_verification()
        scores = await self._reports.list_released_scores()
        active: Dict[str, int] = defaultdict(int)
        completed: Dict[str, int] = defaultdict(int)
        revenue: Dict[str, int] = defaultdict(int)
        score_sum: Dict[str, int] = defaultdict(int)
        score_cnt: Dict[str, int] = defaultdict(int)
        for r in rows:
            state = r["state"] or _UNKNOWN_STATE
            if r["status"] in _ACTIVE_STATES:
                active[state] += 1
            if r["status"] == _COMPLETED:
                completed[state] += 1
            vid = Utils.uuid_to_hex(r["id"])
            revenue[state] += revenue_by_v.get(vid, 0)
            if vid in scores:
                score_sum[state] += scores[vid]
                score_cnt[state] += 1
        states = sorted(set(active) | set(completed) | set(revenue))
        return [
            RegionalRowDto(
                state=state, active=active[state], completed=completed[state],
                revenue_minor=revenue[state],
                avg_trust_score=round(score_sum[state] / score_cnt[state], 1) if score_cnt[state] else None,
            )
            for state in states
        ]

    async def agent_trends(self) -> AgentTrendsDto:
        trend_months = await self._config.get_int(ConfigKey.ANALYTICS_TREND_MONTHS)
        cutoff = Utils.datetime_now() - timedelta(days=30 * trend_months)
        rows = await self._tasks.list_approved_since(cutoff)
        counts: Dict[str, int] = defaultdict(int)
        quality: Dict[str, int] = defaultdict(int)
        for approved_at, review_quality in rows:
            key = approved_at.strftime("%Y-%m")
            counts[key] += 1
            quality[key] += review_quality or 0
        points = [
            AgentTrendPointDto(
                month=month, completed_tasks=counts[month],
                avg_quality=round(quality[month] / counts[month], 1) if counts[month] else None,
            )
            for month in sorted(counts)
        ]
        return AgentTrendsDto(points=points)

    async def whatsapp_channel(self, days: Optional[int] = None) -> WhatsAppChannelAnalyticsDto:
        """§26.10's seven channel metrics over a trailing window (WA-43, D80/D84/D86).

        Lives here rather than in the channel package because this is a **read** surface,
        and the admin analytics API is deliberately one router behind one permission guard
        (D86). The facts it reads are the channel's own (`whatsapp_channel_events`), which
        is why every rate can be recomputed for any window rather than only forward from
        the day a counter was added.

        Windowed, unlike its all-time siblings on this service, because four of the seven
        are rates and a rate with no period is not a number anyone can act on: an
        escalation rate over all time cannot show that last week's flow change worked.
        """
        window_days = days if days and days > 0 else await self._config.get_int(
            ConfigKey.CHANNEL_ANALYTICS_WINDOW_DAYS
        )
        since = Utils.datetime_now() - timedelta(days=window_days)

        counts = await self._channel_events.count_by_type(
            [
                WhatsAppChannelEventType.ENQUIRY,
                WhatsAppChannelEventType.INTAKE_STARTED,
                WhatsAppChannelEventType.INTAKE_COMPLETED,
                WhatsAppChannelEventType.PAYMENT_COMPLETED,
                WhatsAppChannelEventType.ESCALATED,
            ],
            since,
        )
        enquiries = counts[WhatsAppChannelEventType.ENQUIRY.value]
        intake_started = counts[WhatsAppChannelEventType.INTAKE_STARTED.value]
        intake_completed = counts[WhatsAppChannelEventType.INTAKE_COMPLETED.value]
        payment_completed = counts[WhatsAppChannelEventType.PAYMENT_COMPLETED.value]
        escalations = counts[WhatsAppChannelEventType.ESCALATED.value]

        granted = await self._whatsapp_consents.count_granted()
        linked = await self._whatsapp_links.count_active()
        utility = granted[WhatsAppConsentKind.UTILITY.value]
        marketing = granted[WhatsAppConsentKind.MARKETING.value]

        health = await self._whatsapp_number_health.current()

        return WhatsAppChannelAnalyticsDto(
            window_days=window_days,
            intake_completed=intake_completed,
            payment_completed=payment_completed,
            seam_conversion_rate=_rate(payment_completed, intake_completed),
            enquiries=enquiries,
            enquiries_by_page_code=_as_counts(
                await self._channel_events.count_by_page_code(since)
            ),
            intake_started=intake_started,
            enquiry_to_intake_rate=_rate(intake_started, enquiries),
            escalations=escalations,
            escalation_rate=_rate(escalations, enquiries),
            escalations_by_reason=_as_counts(
                await self._channel_events.count_by_escalation_reason(since)
            ),
            linked_numbers=linked,
            utility_opt_ins=utility,
            marketing_opt_ins=marketing,
            utility_opt_in_rate=_rate(utility, linked),
            marketing_opt_in_rate=_rate(marketing, linked),
            number_health=(
                WhatsAppNumberHealthDto(
                    quality_rating=health.quality_rating,
                    messaging_limit_tier=health.messaging_limit_tier,
                    synced_at=health.last_synced_at,
                    sync_error=health.sync_error,
                )
                if health
                else None
            ),
            # §26.6.3 gives voice notes their own escalation reason, but the volume is
            # counted off the inbound journal instead: a voice note from a thread already
            # in `HUMAN` mode never reaches the bot, and §26.10 wants how many arrived, not
            # how many the bot happened to see.
            voice_notes=await self._whatsapp_inbound.count_by_kind(InboundKind.AUDIO, since),
        )


def _as_counts(counted: Dict[str, int]) -> List[ChannelCountDto]:
    """A grouped count as an ordered list — biggest first, which is reading order."""
    return [
        ChannelCountDto(label=label, count=count)
        for label, count in sorted(counted.items(), key=lambda item: (-item[1], item[0]))
    ]
