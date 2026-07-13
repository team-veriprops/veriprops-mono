"""Agent reputation & coverage service (PRD §16, D32/D33).

Derives an agent's metrics on read, owns availability + coverage, and produces the admin's
ranked "suggested agents" list for a task — filtering by role eligibility, credential status,
coverage (role-differentiated), and capacity, then ordering by the composite score.
"""
from __future__ import annotations

from typing import List, Optional

from kink import inject

from main.app.config.settings import settings
from main.app.core.state.status import AgentRole
from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.config.nigeria_locations import is_valid_state
from main.app.domain.property.repo import PropertyRepo
from main.app.domain.system_config.models import ConfigKey
from main.app.domain.system_config.service import ConfigService
from main.app.domain.user.agent.coverage.models import (
    AgentCoverageInputDto,
    CreateAgentCoverageDto,
)
from main.app.domain.user.agent.coverage.repo import AgentCoverageRepo
from main.app.domain.user.agent.credential.repo import AgentCredentialRepo
from main.app.domain.user.agent.credential.rules import active_roles
from main.app.domain.user.agent.profile.models import (
    AgentApplicationStatus,
    AvailabilityStatus,
    UpdateAgentProfileDto,
)
from main.app.domain.user.agent.profile.repo import AgentProfileRepo
from main.app.domain.user.agent.reputation.metrics import AgentMetrics, compute_metrics
from main.app.domain.user.agent.reputation.models import (
    AgentMetricsDto,
    AgentProfileSummaryDto,
    SuggestedAgentDto,
)
from main.app.domain.verification.repo import VerificationRepo
from main.app.domain.verification.task.repo import VerificationTaskRepo
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    ResourceNotFoundException,
    ValidationException,
)

# Roles that are genuinely location-bound (§16.1): coverage must match the property area.
# Registry / Lawyer work is effectively remote, so coverage does not gate their matching.
_LOCATION_BOUND_ROLES = {AgentRole.FIELD, AgentRole.SURVEYOR}


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class AgentReputationService:
    def __init__(
        self,
        profile_repo: AgentProfileRepo,
        coverage_repo: AgentCoverageRepo,
        credential_repo: AgentCredentialRepo,
        task_repo: VerificationTaskRepo,
        verification_repo: VerificationRepo,
        property_repo: PropertyRepo,
        config_service: ConfigService,
        audit_service: AuditLogService,
    ):
        self._profiles = profile_repo
        self._coverage = coverage_repo
        self._credentials = credential_repo
        self._tasks = task_repo
        self._verifications = verification_repo
        self._properties = property_repo
        self._config = config_service
        self._audit = audit_service

    # ── Metrics + profile (agent) ─────────────────────────────────

    async def get_metrics(self, agent_id: str) -> AgentMetricsDto:
        metrics = await self._compute(agent_id)
        return self._metrics_dto(metrics)

    async def get_profile_summary(self, agent_id: str) -> AgentProfileSummaryDto:
        profile = await self._profiles.get_by_user_id(agent_id)
        if profile is None:
            raise ResourceNotFoundException(resource="agent profile")
        metrics = await self._compute(agent_id)
        creds = await self._credentials.list_for_user(agent_id)
        approved = [AgentRole(r) for r in (profile.approved_roles or [])]
        active = active_roles(profile.approved_roles or [], creds, Utils.datetime_now().date())
        active_count = await self._tasks.count_active_for_agent(agent_id)
        coverage = await self._coverage.list_for_user(agent_id)
        wide_threshold = await self._config.get_int(ConfigKey.AGENT_WIDE_COVERAGE_STATES)
        distinct_states = {c.state for c in coverage}
        return AgentProfileSummaryDto(
            metrics=self._metrics_dto(metrics),
            availability=AvailabilityStatus(profile.availability),
            effective_availability=self._effective_availability(profile.availability, active_count),
            active_task_count=active_count,
            max_active_tasks=settings.AGENT_MAX_ACTIVE_TASKS,
            approved_roles=approved,
            active_roles=active,
            coverage=[AgentCoverageInputDto(
                state=c.state, lga=c.lga, place=c.place, travel_radius_km=c.travel_radius_km,
            ) for c in coverage],
            coverage_flagged_for_review=len(distinct_states) > wide_threshold,
        )

    async def set_availability(self, agent_id: str, availability: AvailabilityStatus) -> AvailabilityStatus:
        profile = await self._profiles.get_by_user_id(agent_id)
        if profile is None:
            raise ResourceNotFoundException(resource="agent profile")
        await self._profiles.update(profile.id, UpdateAgentProfileDto(availability=availability.value))
        self._audit.schedule(
            action=AuditActionType.AGENT_AVAILABILITY_CHANGED,
            resource_type="agent_profile", resource_id=profile.id, actor_id=agent_id,
            details={"availability": availability.value},
        )
        active_count = await self._tasks.count_active_for_agent(agent_id)
        return self._effective_availability(availability.value, active_count)

    # ── Coverage (agent-declared, §16.1) ──────────────────────────

    async def list_coverage(self, agent_id: str) -> List[AgentCoverageInputDto]:
        rows = await self._coverage.list_for_user(agent_id)
        return [AgentCoverageInputDto(
            state=c.state, lga=c.lga, place=c.place, travel_radius_km=c.travel_radius_km,
        ) for c in rows]

    async def set_coverage(
        self, agent_id: str, areas: List[AgentCoverageInputDto]
    ) -> List[AgentCoverageInputDto]:
        """Replace an agent's declared coverage (§16.1). States are validated against the
        canon; unusually wide coverage is *flagged for review*, never rejected. Takes immediate
        effect on new matching."""
        for area in areas:
            if not is_valid_state(area.state):
                raise ValidationException(message=f"Unknown state: {area.state}")
        for existing in await self._coverage.list_for_user(agent_id):
            await self._coverage.soft_delete(existing.id)
        saved: List[AgentCoverageInputDto] = []
        for area in areas:
            state = area.state.strip().lower()
            await self._coverage.create(CreateAgentCoverageDto(
                user_id=agent_id, state=state, lga=area.lga,
                place=area.place, travel_radius_km=area.travel_radius_km,
            ))
            saved.append(AgentCoverageInputDto(
                state=state, lga=area.lga, place=area.place, travel_radius_km=area.travel_radius_km,
            ))
        wide_threshold = await self._config.get_int(ConfigKey.AGENT_WIDE_COVERAGE_STATES)
        distinct = {a.state for a in saved}
        self._audit.schedule(
            action=AuditActionType.AGENT_COVERAGE_UPDATED,
            resource_type="agent_coverage", resource_id=agent_id, actor_id=agent_id,
            details={"states": sorted(distinct), "flagged": len(distinct) > wide_threshold},
        )
        # Echo the just-written coverage (a same-transaction re-list can read stale rows).
        return saved

    # ── Suggested agents (admin ranking) ──────────────────────────

    async def suggested_agents(self, verification_id: str, role: AgentRole) -> List[SuggestedAgentDto]:
        """Ranked eligible agents for a role on a verification (§16.1). Filters by role
        eligibility + credential status + coverage (role-differentiated) + capacity, ordered
        by composite score. Feeds the admin assignment picker."""
        # TODO(gap): low-performance visibility reduction applies only to this ranking — the
        # broadcast pool is untargeted accept-by-id, so per-agent pool-feed reduction needs a
        # targeted/browsable pool — PRD "Known Gaps & Roadmap".
        verification = await self._verifications.get_model(verification_id)
        if verification is None:
            raise ResourceNotFoundException(resource="verification")
        area_state = await self._property_state(verification.property_id)

        low_threshold = await self._config.get_int(ConfigKey.AGENT_LOW_PERFORMANCE_THRESHOLD)
        top_threshold = await self._config.get_int(ConfigKey.AGENT_TOP_AGENT_ACCURACY_THRESHOLD)
        today = Utils.datetime_now().date()

        candidates: List[SuggestedAgentDto] = []
        for profile in await self._profiles.list_by_status(AgentApplicationStatus.APPROVED.value):
            creds = await self._credentials.list_for_user(profile.user_id)
            if role not in active_roles(profile.approved_roles or [], creds, today):
                continue  # role not approved or its credential is suspended/expired
            coverage = await self._coverage.list_for_user(profile.user_id)
            covers = self._covers_area(coverage, area_state)
            if role in _LOCATION_BOUND_ROLES and not covers:
                continue  # Field/Surveyor must be in-area
            active_count = await self._tasks.count_active_for_agent(profile.user_id)
            if active_count >= settings.AGENT_MAX_ACTIVE_TASKS:
                continue  # at capacity (§6.5)

            metrics = await self._compute(profile.user_id)
            name = await self._agent_name(profile.user_id)
            candidates.append(SuggestedAgentDto(
                user_id=profile.user_id, name=name,
                composite_score=metrics.composite_score, accuracy_score=metrics.accuracy_score,
                completion_rate=metrics.completion_rate, timeliness_rate=metrics.timeliness_rate,
                availability=self._effective_availability(profile.availability, active_count),
                active_task_count=active_count, covers_area=covers,
                top_agent=metrics.avg_quality >= top_threshold,
                low_performance=metrics.composite_score < low_threshold,
            ))
        # Low performers sink to the bottom, then order by composite desc (§16.1).
        candidates.sort(key=lambda c: (not c.low_performance, c.composite_score), reverse=True)
        return candidates

    # ── helpers ───────────────────────────────────────────────────

    async def _compute(self, agent_id: str) -> AgentMetrics:
        tasks = await self._tasks.list_all_for_agent(agent_id)
        task_sla_hours = await self._config.get_int(ConfigKey.TASK_SLA_HOURS)
        return compute_metrics(tasks, task_sla_hours)

    async def _property_state(self, property_id: Optional[str]) -> Optional[str]:
        if not property_id:
            return None
        prop = await self._properties.get_model(property_id)
        return prop.state if prop is not None else None

    async def _agent_name(self, user_id: str) -> str:
        from kink import di
        from main.app.domain.user.service import UserService
        user = await di[UserService].get_user_model(user_id)
        return f"{user.first_name} {user.last_name}".strip() if user else ""

    @staticmethod
    def _covers_area(coverage, area_state: Optional[str]) -> bool:
        if not area_state:
            return True  # unknown area — don't exclude
        target = area_state.strip().lower()
        return any((c.state or "").strip().lower() == target for c in coverage)

    @staticmethod
    def _effective_availability(set_value: str, active_count: int) -> AvailabilityStatus:
        if active_count >= settings.AGENT_MAX_ACTIVE_TASKS:
            return AvailabilityStatus.RED
        return AvailabilityStatus(set_value)

    @staticmethod
    def _metrics_dto(m: AgentMetrics) -> AgentMetricsDto:
        return AgentMetricsDto(
            total_jobs=m.total_jobs, completed_jobs=m.completed_jobs,
            completion_rate=m.completion_rate, accuracy_score=m.accuracy_score,
            avg_quality=m.avg_quality, timeliness_rate=m.timeliness_rate,
            decline_count=m.decline_count, composite_score=m.composite_score,
            active_since=m.active_since,
        )
