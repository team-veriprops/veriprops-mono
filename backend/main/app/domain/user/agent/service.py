"""Agent onboarding service (PRD §3.1–3.2, §3.3a).

Owns the resumable application wizard, submission (KYC + credentials + coverage +
AGENT_TERMS consent + AGENT persona + PENDING profile), the applicant's status
view, the admin approval queue, and role-level credential-expiry suspension.
"""
from __future__ import annotations

import json
from datetime import timedelta
from typing import List, Optional

from kink import inject

from main.app.core.state.status import AgentRole
from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.user.agent.credentials import active_roles
from main.app.domain.user.agent.kyc_service import KycService
from main.app.domain.user.agent.models import (
    AgentApplicationDetailDto,
    AgentApplicationDraftDto,
    AgentApplicationStatus,
    AgentApplicationStatusDto,
    AgentApplicationSummaryDto,
    AgentCoverageInputDto,
    AgentCredentialDto,
    AgentProfile,
    ApproveAgentApplicationDto,
    CreateAgentApplicationDraftDto,
    CreateAgentCoverageDto,
    CreateAgentCredentialDto,
    CreateAgentProfileDto,
    CredentialStatus,
    KycRecordDto,
    RejectAgentApplicationDto,
    SaveAgentApplicationDraftDto,
    SubmitAgentApplicationDto,
    UpdateAgentApplicationDraftDto,
    UpdateAgentCredentialDto,
    UpdateAgentProfileDto,
)
from main.app.domain.user.agent.repo import (
    AgentApplicationDraftRepo,
    AgentCoverageRepo,
    AgentCredentialRepo,
    AgentProfileRepo,
)
from main.app.domain.user.agent.validator import AgentApplicationValidator
from main.app.domain.user.auth.consent.models import ConsentDocumentType
from main.app.domain.user.auth.consent.service import ConsentService
from main.app.domain.user.auth.session.models import UserPersona
from main.app.domain.user.service import UserService
from main.appodus_utils import Utils
from main.appodus_utils.db.models import Page, PaginationMeta
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import ResourceNotFoundException

_DRAFT_TTL_DAYS = 30


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class AgentService:
    def __init__(
        self,
        profile_repo: AgentProfileRepo,
        credential_repo: AgentCredentialRepo,
        coverage_repo: AgentCoverageRepo,
        draft_repo: AgentApplicationDraftRepo,
        kyc_service: KycService,
        user_service: UserService,
        consent_service: ConsentService,
        audit_service: AuditLogService,
        validator: AgentApplicationValidator,
    ):
        self._profile_repo = profile_repo
        self._credential_repo = credential_repo
        self._coverage_repo = coverage_repo
        self._draft_repo = draft_repo
        self._kyc_service = kyc_service
        self._user_service = user_service
        self._consent_service = consent_service
        self._audit_service = audit_service
        self._validator = validator

    # ── Resumable wizard draft ────────────────────────────────────

    async def get_draft(self, user_id: str) -> Optional[AgentApplicationDraftDto]:
        draft = await self._draft_repo.get_active_for_user(user_id)
        if not draft:
            return None
        return AgentApplicationDraftDto(
            step=draft.step,
            payload=json.loads(draft.payload) if draft.payload else {},
            date_updated=draft.date_updated or draft.date_created,
        )

    async def save_draft(self, user_id: str, dto: SaveAgentApplicationDraftDto) -> AgentApplicationDraftDto:
        payload_json = json.dumps(dto.payload)
        existing = await self._draft_repo.get_active_for_user(user_id)
        if existing:
            await self._draft_repo.update(
                existing.id, UpdateAgentApplicationDraftDto(step=dto.step, payload=payload_json)
            )
        else:
            await self._draft_repo.create(CreateAgentApplicationDraftDto(
                user_id=user_id,
                step=dto.step,
                payload=payload_json,
                expires_at=Utils.datetime_now() + timedelta(days=_DRAFT_TTL_DAYS),
            ))
        return AgentApplicationDraftDto(step=dto.step, payload=dto.payload, date_updated=Utils.datetime_now())

    async def _discard_draft(self, user_id: str) -> None:
        existing = await self._draft_repo.get_active_for_user(user_id)
        if existing:
            await self._draft_repo.soft_delete(existing.id)

    # ── Submission ────────────────────────────────────────────────

    async def submit_application(
        self, user_id: str, dto: SubmitAgentApplicationDto, ip_address: Optional[str] = None
    ) -> AgentApplicationStatusDto:
        self._validator.validate_submission(dto)
        user = await self._user_service.get_user_model(user_id)

        # KYC first — persists the provider result (no raw biometrics).
        await self._kyc_service.run_verification(
            user_id, user.first_name, user.last_name, dto.kyc
        )

        profile = await self._profile_repo.create_return_model(CreateAgentProfileDto(
            user_id=user_id,
            roles=dto.roles,
            status=AgentApplicationStatus.PENDING,
            bio=dto.bio,
            years_experience=dto.years_experience,
            submitted_at=Utils.datetime_now(),
        ))

        for cred in dto.credentials:
            await self._credential_repo.create(CreateAgentCredentialDto(
                user_id=user_id,
                role=cred.role,
                credential_type=cred.credential_type,
                licence_number=cred.licence_number,
                document_ref=cred.document_ref,
                expiry_date=cred.expiry_date,
                status=CredentialStatus.PENDING,
            ))

        for cov in dto.coverage:
            await self._coverage_repo.create(CreateAgentCoverageDto(
                user_id=user_id,
                state=cov.state,
                lga=cov.lga,
                place=cov.place,
                travel_radius_km=cov.travel_radius_km,
            ))

        # AGENT_TERMS acceptance (PRD §3.5 versioned consent).
        await self._consent_service.record_user_consent(
            user_id=user_id,
            document_type=ConsentDocumentType.AGENT_TERMS,
            consent_version=dto.agent_terms_version,
            ip_address=ip_address,
        )

        # Persona is additive (PRD §3.2) — grants the AGENT hat without removing CUSTOMER.
        await self._user_service.add_persona(user_id, UserPersona.AGENT)

        await self._discard_draft(user_id)

        self._audit_service.schedule(
            action=AuditActionType.AGENT_APPLICATION_SUBMITTED,
            resource_type="agent_profile",
            resource_id=profile.id,
            actor_id=user_id,
            to_state=AgentApplicationStatus.PENDING.value,
            details={"roles": [r.value for r in dto.roles]},
            ip_address=ip_address,
        )

        return await self._status_dto(profile)

    # ── Applicant status view ─────────────────────────────────────

    async def get_my_status(self, user_id: str) -> Optional[AgentApplicationStatusDto]:
        profile = await self._profile_repo.get_by_user_id(user_id)
        if not profile:
            return None
        return await self._status_dto(profile)

    async def _status_dto(self, profile: AgentProfile) -> AgentApplicationStatusDto:
        creds = await self._credential_repo.list_for_user(profile.user_id)
        approved = list(profile.approved_roles or [])
        return AgentApplicationStatusDto(
            status=AgentApplicationStatus(profile.status),
            roles=[AgentRole(r) for r in (profile.roles or [])],
            approved_roles=[AgentRole(r) for r in approved],
            active_roles=active_roles(approved, creds, Utils.datetime_now().date()),
            rejection_reason=profile.rejection_reason,
            submitted_at=profile.submitted_at,
        )

    # ── Admin approval queue ──────────────────────────────────────

    async def list_applications(
        self, status: Optional[str] = None, page: int = 0, page_size: int = 10
    ) -> Page[AgentApplicationSummaryDto]:
        rows, total = await self._profile_repo.page_applications(
            status=status, offset=page * page_size, limit=page_size
        )
        items: List[AgentApplicationSummaryDto] = []
        for p in rows:
            user = await self._user_service.get_user_model(p.user_id)
            items.append(AgentApplicationSummaryDto(
                id=p.id,
                user_id=p.user_id,
                applicant_name=f"{user.first_name} {user.last_name}".strip() if user else "",
                roles=[AgentRole(r) for r in (p.roles or [])],
                status=AgentApplicationStatus(p.status),
                submitted_at=p.submitted_at,
            ))
        total_pages = (total + page_size - 1) // page_size if page_size else 0
        return Page[AgentApplicationSummaryDto](
            items=items,
            meta=PaginationMeta(
                page=page,
                page_size=page_size,
                count=len(items),
                total=total,
                total_pages=total_pages,
                prev_page=page - 1 if page > 0 else None,
                next_page=page + 1 if (page + 1) < total_pages else None,
            ),
        )

    async def get_application_detail(self, profile_id: str) -> AgentApplicationDetailDto:
        profile = await self._profile_repo.get_model(profile_id)
        if not profile:
            raise ResourceNotFoundException(resource="agent application")
        user = await self._user_service.get_user_model(profile.user_id)
        creds = await self._credential_repo.list_for_user(profile.user_id)
        coverage = await self._coverage_repo.list_for_user(profile.user_id)
        kyc = await self._kyc_service.get_latest(profile.user_id)
        return AgentApplicationDetailDto(
            id=profile.id,
            user_id=profile.user_id,
            applicant_name=f"{user.first_name} {user.last_name}".strip() if user else "",
            applicant_email=user.email if user else "",
            roles=[AgentRole(r) for r in (profile.roles or [])],
            approved_roles=[AgentRole(r) for r in (profile.approved_roles or [])],
            status=AgentApplicationStatus(profile.status),
            rejection_reason=profile.rejection_reason,
            bio=profile.bio,
            years_experience=profile.years_experience,
            submitted_at=profile.submitted_at,
            credentials=[AgentCredentialDto(
                role=AgentRole(c.role),
                credential_type=c.credential_type,
                licence_number=c.licence_number,
                expiry_date=c.expiry_date,
                status=CredentialStatus(c.status),
            ) for c in creds],
            coverage=[AgentCoverageInputDto(
                state=c.state, lga=c.lga, place=c.place, travel_radius_km=c.travel_radius_km,
            ) for c in coverage],
            kyc=KycRecordDto(
                provider=kyc.provider, method=kyc.method, status=kyc.status,
                score=kyc.score, summary=kyc.summary, verified_at=kyc.verified_at,
            ) if kyc else None,
        )

    async def approve_application(
        self, profile_id: str, dto: ApproveAgentApplicationDto, admin_id: str
    ) -> AgentApplicationDetailDto:
        profile = await self._profile_repo.get_model(profile_id)
        if not profile:
            raise ResourceNotFoundException(resource="agent application")

        applied = [AgentRole(r) for r in (profile.roles or [])]
        approved = dto.approved_roles if dto.approved_roles else applied
        # Never approve a role the applicant did not apply for.
        approved = [r for r in approved if r in applied]

        await self._profile_repo.update(profile_id, UpdateAgentProfileDto(
            status=AgentApplicationStatus.APPROVED.value,
            approved_roles=[r.value for r in approved],
            reviewed_by=admin_id,
        ))
        await self._mark_reviewed(profile_id)

        # Clear pending credentials for the approved roles.
        for cred in await self._credential_repo.list_for_user(profile.user_id):
            if AgentRole(cred.role) in approved and cred.status == CredentialStatus.PENDING.value:
                await self._credential_repo.update(
                    cred.id, UpdateAgentCredentialDto(status=CredentialStatus.VERIFIED.value)
                )

        self._audit_service.schedule(
            action=AuditActionType.AGENT_APPLICATION_APPROVED,
            resource_type="agent_profile",
            resource_id=profile_id,
            actor_id=admin_id,
            from_state=profile.status,
            to_state=AgentApplicationStatus.APPROVED.value,
            details={"approved_roles": [r.value for r in approved]},
        )
        return await self.get_application_detail(profile_id)

    async def reject_application(
        self, profile_id: str, dto: RejectAgentApplicationDto, admin_id: str
    ) -> AgentApplicationDetailDto:
        profile = await self._profile_repo.get_model(profile_id)
        if not profile:
            raise ResourceNotFoundException(resource="agent application")

        await self._profile_repo.update(profile_id, UpdateAgentProfileDto(
            status=AgentApplicationStatus.REJECTED.value,
            rejection_reason=dto.reason,
            reviewed_by=admin_id,
        ))
        await self._mark_reviewed(profile_id)

        self._audit_service.schedule(
            action=AuditActionType.AGENT_APPLICATION_REJECTED,
            resource_type="agent_profile",
            resource_id=profile_id,
            actor_id=admin_id,
            from_state=profile.status,
            to_state=AgentApplicationStatus.REJECTED.value,
            details={"reason": dto.reason},
        )
        return await self.get_application_detail(profile_id)

    async def _mark_reviewed(self, profile_id: str) -> None:
        # reviewed_at is a datetime → set directly on the model (the update DTO
        # path json-encodes datetimes; see CLAUDE.md GenericRepo note).
        profile = await self._profile_repo.get_model(profile_id)
        profile.reviewed_at = Utils.datetime_now()

    # ── Role-level credential-expiry suspension (§3.3a) ───────────

    async def suspend_expired_role_credentials(self, user_id: str) -> List[AgentRole]:
        """Flag any expired credentials so only the affected role is suspended.

        Returns the roles that ended up suspended.
        """
        today = Utils.datetime_now().date()
        creds = await self._credential_repo.list_for_user(user_id)
        suspended: List[AgentRole] = []
        for cred in creds:
            if (
                cred.expiry_date is not None
                and cred.expiry_date < today
                and cred.status != CredentialStatus.EXPIRED.value
            ):
                await self._credential_repo.update(
                    cred.id, UpdateAgentCredentialDto(status=CredentialStatus.EXPIRED.value)
                )
                suspended.append(AgentRole(cred.role))
        return suspended
