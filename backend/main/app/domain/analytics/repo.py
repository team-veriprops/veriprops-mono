"""Analytics repo — aggregation-only, no GenericRepo. S53."""
from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from kink import inject
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.analytics.models import (
    AgentPerformanceTrendDto,
    AvgVerificationTimeByTierDto,
    ConversionFunnelDto,
    DisputeRateDto,
    MissionControlDto,
    RegionalPerformanceDto,
    RegionalStat,
    RevenueByLocationDto,
)
from main.app.domain.user.agent.models import AgentApplication, AvailabilityStatus
from main.app.domain.user.auth.session.models import UserPersona
from main.app.domain.user.models import User
from main.app.domain.verification.dispute.models import Dispute
from main.app.domain.verification.models import Verification, VerificationStatus
from main.app.domain.verification.task.models import Task, TaskStatus
from main.app.domain.payment.models import Payment, PaymentStatus
from main.appodus_utils.db.session import get_db_session_from_context


@inject
class AnalyticsRepo:
    def __init__(self, db: AsyncSession):
        self._db = db

    @property
    def _session(self) -> AsyncSession:
        return get_db_session_from_context()

    async def mission_control(self, stuck_threshold_hours: int = 48) -> MissionControlDto:
        session = self._session

        active_statuses = [VerificationStatus.IN_PROGRESS.value, VerificationStatus.UNDER_REVIEW.value]
        active_count_q = await session.scalar(
            select(func.count(Verification.id)).where(
                Verification.status.in_(active_statuses),
                Verification.deleted == False,
            )
        )

        pending_q = await session.scalar(
            select(func.count(Task.id)).where(
                Task.status == TaskStatus.PENDING.value,
                Task.pool_released_at.is_not(None),
                Task.deleted == False,
            )
        )

        stuck_q = await session.scalar(
            text(
                "SELECT COUNT(*) FROM tasks "
                "WHERE status = 'IN_PROGRESS' AND deleted = 0 "
                "AND accepted_at < NOW() - INTERVAL :hours HOUR"
            ),
            {"hours": stuck_threshold_hours},
        )

        sla_q = await session.scalar(
            text(
                "SELECT COUNT(*) FROM tasks "
                "WHERE status IN ('ACCEPTED', 'IN_PROGRESS') AND deleted = 0 "
                "AND accepted_at < NOW() - INTERVAL :hours HOUR"
            ),
            {"hours": int(stuck_threshold_hours * 0.8)},
        )

        revenue_q = await session.scalar(
            select(func.sum(Payment.amount_minor)).where(
                Payment.status == PaymentStatus.SUCCEEDED.value,
                Payment.deleted == False,
            )
        )
        revenue_ngn = float((revenue_q or 0) / 100)

        available_q = await session.scalar(
            select(func.count(AgentApplication.id)).where(
                AgentApplication.availability_status == AvailabilityStatus.AVAILABLE.value,
                AgentApplication.deleted == False,
            )
        )

        return MissionControlDto(
            active_verifications=int(active_count_q or 0),
            pending_assignments=int(pending_q or 0),
            stuck_jobs=int(stuck_q or 0),
            sla_at_risk_count=int(sla_q or 0),
            revenue_total_ngn=revenue_ngn,
            available_agents=int(available_q or 0),
        )

    async def regional_performance(self) -> RegionalPerformanceDto:
        session = self._session
        rows = await session.execute(
            text(
                """
                SELECT
                    p.state AS region,
                    COUNT(CASE WHEN v.status IN ('IN_PROGRESS','UNDER_REVIEW','PAID') THEN 1 END) AS active_count,
                    COUNT(CASE WHEN v.status = 'COMPLETED' THEN 1 END) AS completed_count,
                    AVG(v.trust_score) AS avg_trust_score,
                    COALESCE(SUM(CASE WHEN pay.status = 'SUCCEEDED' THEN pay.amount_minor ELSE 0 END), 0) / 100 AS revenue_ngn
                FROM verifications v
                JOIN properties p ON p.id = v.property_id AND p.deleted = 0
                LEFT JOIN payments pay ON pay.verification_id = v.id AND pay.deleted = 0
                WHERE v.deleted = 0
                GROUP BY p.state
                ORDER BY completed_count DESC
                """
            )
        )
        regions = [
            RegionalStat(
                region=r.region,
                active_count=int(r.active_count or 0),
                completed_count=int(r.completed_count or 0),
                avg_trust_score=float(r.avg_trust_score) if r.avg_trust_score is not None else None,
                revenue_ngn=float(r.revenue_ngn or 0),
            )
            for r in rows
        ]
        return RegionalPerformanceDto(regions=regions)

    async def conversion_funnel(self) -> ConversionFunnelDto:
        session = self._session
        from main.app.domain.user.auth.session.models import UserPersona

        signups = await session.scalar(
            text("SELECT COUNT(*) FROM users WHERE JSON_CONTAINS(personas, '\"CUSTOMER\"') AND deleted = 0")
        )
        submitted = await session.scalar(
            select(func.count(Verification.id)).where(
                Verification.status != VerificationStatus.DRAFT.value,
                Verification.deleted == False,
            )
        )
        paid = await session.scalar(
            select(func.count(Verification.id)).where(
                Verification.payment_id.is_not(None),
                Verification.status.not_in([
                    VerificationStatus.DRAFT.value,
                    VerificationStatus.SUBMITTED.value,
                    VerificationStatus.PAYMENT_PENDING.value,
                ]),
                Verification.deleted == False,
            )
        )
        completed = await session.scalar(
            select(func.count(Verification.id)).where(
                Verification.status == VerificationStatus.COMPLETED.value,
                Verification.deleted == False,
            )
        )

        signups_n = int(signups or 0)
        paid_n = int(paid or 0)
        completed_n = int(completed or 0)

        signup_to_paid_pct = round(paid_n / signups_n * 100, 1) if signups_n else 0.0
        paid_to_completed_pct = round(completed_n / paid_n * 100, 1) if paid_n else 0.0

        return ConversionFunnelDto(
            signups=signups_n,
            submitted=int(submitted or 0),
            paid=paid_n,
            completed=completed_n,
            signup_to_paid_pct=signup_to_paid_pct,
            paid_to_completed_pct=paid_to_completed_pct,
        )

    async def avg_verification_time_by_tier(self) -> List[AvgVerificationTimeByTierDto]:
        session = self._session
        rows = await session.execute(
            text(
                """
                SELECT tier,
                       AVG(TIMESTAMPDIFF(SECOND, paid_at, completed_at)) / 3600 AS avg_hours
                FROM verifications
                WHERE status = 'COMPLETED'
                  AND paid_at IS NOT NULL
                  AND completed_at IS NOT NULL
                  AND deleted = 0
                GROUP BY tier
                """
            )
        )
        return [
            AvgVerificationTimeByTierDto(tier=r.tier, avg_hours=round(float(r.avg_hours or 0), 1))
            for r in rows
        ]

    async def agent_performance_trends(self, months: int = 6) -> List[AgentPerformanceTrendDto]:
        session = self._session
        rows = await session.execute(
            text(
                """
                SELECT DATE_FORMAT(date_created, '%Y-%m') AS period,
                       AVG(score) AS avg_quality_score,
                       COUNT(*) AS total_scores
                FROM agent_quality_scores
                WHERE deleted = 0
                  AND date_created >= NOW() - INTERVAL :months MONTH
                GROUP BY period
                ORDER BY period ASC
                """,
            ),
            {"months": months},
        )
        return [
            AgentPerformanceTrendDto(
                period=r.period,
                avg_quality_score=round(float(r.avg_quality_score or 0), 2),
                total_scores=int(r.total_scores or 0),
            )
            for r in rows
        ]

    async def revenue_by_location(self) -> List[RevenueByLocationDto]:
        session = self._session
        rows = await session.execute(
            text(
                """
                SELECT p.state, v.tier,
                       SUM(pay.amount_minor) / 100 AS revenue_ngn,
                       COUNT(DISTINCT v.id) AS count
                FROM verifications v
                JOIN properties p ON p.id = v.property_id AND p.deleted = 0
                JOIN payments pay ON pay.verification_id = v.id
                    AND pay.status = 'SUCCEEDED' AND pay.deleted = 0
                WHERE v.deleted = 0
                GROUP BY p.state, v.tier
                ORDER BY revenue_ngn DESC
                """
            )
        )
        return [
            RevenueByLocationDto(
                state=r.state,
                tier=r.tier,
                revenue_ngn=float(r.revenue_ngn or 0),
                count=int(r.count or 0),
            )
            for r in rows
        ]

    async def dispute_rate(self) -> DisputeRateDto:
        session = self._session
        total_completed = await session.scalar(
            select(func.count(Verification.id)).where(
                Verification.status == VerificationStatus.COMPLETED.value,
                Verification.deleted == False,
            )
        )
        total_disputed = await session.scalar(
            select(func.count(Verification.id)).where(
                Verification.status == VerificationStatus.DISPUTED.value,
                Verification.deleted == False,
            )
        )
        total_c = int(total_completed or 0)
        total_d = int(total_disputed or 0)
        denom = total_c + total_d
        rate = round(total_d / denom * 100, 1) if denom else 0.0
        return DisputeRateDto(
            total_completed=total_c,
            total_disputed=total_d,
            dispute_rate_pct=rate,
        )
