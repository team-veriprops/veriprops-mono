"""Agent application service.

Owns the wizard step transitions, KYC flow orchestration, and admin
approve/reject. On approval the AGENT persona is appended to the user record.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

from typing import List, Optional

from kink import di, inject

from main.app.config.settings import settings
from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.user.agent.kyc.interface import (
    BvnVerificationResult,
    KycProvider,
    SelfieMatchResult,
)
from main.app.domain.user.agent.models import (
    AdminAgentApplicationDto,
    AgentApplication,
    AgentApplicationDto,
    AgentApplicationStatus,
    AgentType,
    BvnVerifyDto,
    BvnVerificationResultDto,
    CreateAgentApplicationDto,
    CredentialsStepDto,
    IdDocType,
    KycDocumentsDto,
    KycMethod,
    SearchAgentApplicationDto,
    SubmitApplicationDto,
    TypesStepDto,
    UpdateAgentApplicationDto,
)
from main.app.domain.user.agent.repo import AgentApplicationRepo
from main.app.domain.user.agent.validator import AgentApplicationValidator
from main.app.domain.user.auth.consent.models import ConsentDocumentType
from main.app.domain.user.auth.consent.service import ConsentService
from main.app.domain.user.auth.session.models import (
    SecurityEventType,
    UserPersona,
)
from main.app.domain.user.auth.session.service import SessionService
from main.app.domain.user.service import UserService
from main.appodus_utils import Utils
from main.appodus_utils.db.models import Page
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    ResourceNotFoundException,
    ValidationException,
)

logger: Logger = di["logger"]


# Agent KYC artefacts use a dedicated S3 prefix for per-user access scoping.
KYC_OBJECT_PREFIX = "agent-kyc"


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class AgentApplicationService:
    def __init__(
        self,
        repo: AgentApplicationRepo,
        validator: AgentApplicationValidator,
        consent_service: ConsentService,
        user_service: UserService,
        session_service: SessionService,
        kyc_provider: KycProvider,
        audit: AuditLogService,
    ):
        self._repo = repo
        self._validator = validator
        self._consent_service = consent_service
        self._user_service = user_service
        self._session_service = session_service
        self._kyc = kyc_provider
        self._audit = audit

    # ── Reads ──────────────────────────────────────────────────────

    async def get_or_create_for_user(self, user_id: str) -> AgentApplicationDto:
        row = await self._repo.get_by_user_id(user_id)
        if row is None:
            await self._repo.create(CreateAgentApplicationDto(
                user_id=user_id,
                status=AgentApplicationStatus.DRAFT,
            ))
            row = await self._repo.get_by_user_id(user_id)
        return self._to_public_dto(row)

    async def get_for_user(self, user_id: str) -> Optional[AgentApplicationDto]:
        row = await self._repo.get_by_user_id(user_id)
        return self._to_public_dto(row) if row else None

    async def list_for_admin(
        self, status: Optional[AgentApplicationStatus] = None, page: int = 1, page_size: int = 25,
    ) -> Page[AdminAgentApplicationDto]:
        # Reuse generic search; map results to admin DTO with user fields filled.
        search = SearchAgentApplicationDto(page=page, page_size=page_size)
        if status:
            search.status = status.value
        result = await self._repo.get_page(search)

        items: List[AdminAgentApplicationDto] = []
        for q in result.items:
            row = await self._repo.get_model(q.id)
            if not row:
                continue
            user = await self._user_service.get_user_model(row.user_id)
            items.append(self._to_admin_dto(row, user))
        return Page[AdminAgentApplicationDto](items=items, meta=result.meta)

    # ── Wizard steps ───────────────────────────────────────────────

    async def update_types(self, user_id: str, dto: TypesStepDto) -> AgentApplicationDto:
        await self.get_or_create_for_user(user_id)  # ensure exists
        row = await self._repo.get_by_user_id(user_id)
        self._validator.assert_mutable(row)
        self._validator.assert_types(dto.types)
        await self._repo.update(str(row.id), UpdateAgentApplicationDto(
            types=dto.types,
        ))
        return self._to_public_dto(await self._repo.get_by_user_id(user_id))

    async def verify_bvn(self, user_id: str, dto: BvnVerifyDto) -> BvnVerificationResultDto:
        row = await self._repo.get_by_user_id(user_id)
        if row is None:
            raise ResourceNotFoundException(resource="AgentApplication")
        self._validator.assert_mutable(row)
        self._validator.assert_bvn(dto.bvn)

        result: BvnVerificationResult = await self._kyc.verify_bvn(dto.bvn)
        last4 = dto.bvn[-4:]
        if not result.verified:
            return BvnVerificationResultDto(
                verified=False,
                bvn_last4=last4,
                failure_reason=result.failure_reason,
            )
        await self._repo.update(str(row.id), UpdateAgentApplicationDto(
            kyc_method=KycMethod.BVN,
            bvn_last4=last4,
            bvn_verification_id=result.verification_id,
            bvn_verified_at=Utils.datetime_now(),
            # Clear ID-doc artefacts if user previously chose that path
            id_doc_type=None,
            id_doc_url=None,
            selfie_url=None,
        ))
        return BvnVerificationResultDto(
            verified=True,
            bvn_last4=last4,
            verification_id=result.verification_id,
        )

    async def record_kyc_documents(
        self, user_id: str, dto: KycDocumentsDto,
    ) -> AgentApplicationDto:
        row = await self._repo.get_by_user_id(user_id)
        if row is None:
            raise ResourceNotFoundException(resource="AgentApplication")
        self._validator.assert_mutable(row)
        if not dto.id_doc_url or not dto.selfie_url:
            raise ValidationException(
                message="ID document and selfie URLs are required",
            )
        # Selfie match — the URLs reference S3 keys uploaded directly by the
        # frontend. We delegate the actual blob fetch + matching to the KYC
        # provider in a real implementation; for the stub, pass empty bytes
        # to exercise the deterministic path.
        match: SelfieMatchResult = await self._kyc.match_selfie(b"\x00")  # stub-friendly
        await self._repo.update(str(row.id), UpdateAgentApplicationDto(
            kyc_method=KycMethod.ID_DOC,
            id_doc_type=dto.id_doc_type,
            id_doc_url=dto.id_doc_url,
            selfie_url=dto.selfie_url,
            selfie_match_score=match.score,
            selfie_matched_at=Utils.datetime_now() if match.matched else None,
            # Clear BVN if user previously chose that path
            bvn_last4=None,
            bvn_verification_id=None,
            bvn_verified_at=None,
        ))
        return self._to_public_dto(await self._repo.get_by_user_id(user_id))

    async def update_credentials(
        self, user_id: str, dto: CredentialsStepDto,
    ) -> AgentApplicationDto:
        row = await self._repo.get_by_user_id(user_id)
        if row is None:
            raise ResourceNotFoundException(resource="AgentApplication")
        self._validator.assert_mutable(row)
        self._validator.assert_credentials(list(row.types or []), dto)
        await self._repo.update(str(row.id), UpdateAgentApplicationDto(
            surveyor_licence_no=dto.surveyor_licence_no,
            surveyor_licence_url=dto.surveyor_licence_url,
            nba_licence_no=dto.nba_licence_no,
            nba_licence_url=dto.nba_licence_url,
            years_of_experience=dto.years_of_experience,
            coverage_states=[s.upper() for s in dto.coverage_states],
            coverage_lgas=list(dto.coverage_lgas or []),
            bio=dto.bio,
        ))
        return self._to_public_dto(await self._repo.get_by_user_id(user_id))

    async def submit(
        self, user_id: str, dto: SubmitApplicationDto,
        ip_address: Optional[str] = None,
        device_fingerprint: Optional[str] = None,
    ) -> AgentApplicationDto:
        if not dto.truthfulness_acknowledged:
            raise ValidationException(message="You must acknowledge the truthfulness statement")
        row = await self._repo.get_by_user_id(user_id)
        if row is None:
            raise ResourceNotFoundException(resource="AgentApplication")
        self._validator.assert_mutable(row)
        self._validator.assert_submission_ready(row)

        # Record versioned consent — frontend must echo back the consent_version
        # the user actually saw at acceptance time.
        await self._consent_service.record_user_consent(
            user_id=user_id,
            document_type=ConsentDocumentType.AGENT_TERMS,
            consent_version=dto.agent_terms_consent_version,
            ip_address=ip_address,
            device_fingerprint=device_fingerprint,
        )

        await self._repo.update(str(row.id), UpdateAgentApplicationDto(
            status=AgentApplicationStatus.PENDING,
            truthfulness_acknowledged="ACKNOWLEDGED",
            submitted_at=Utils.datetime_now(),
        ))
        await self._record_security_event(
            user_id=user_id,
            type_=SecurityEventType.AGENT_APPLICATION_SUBMITTED,
            description=f"submitted application {row.id}",
        )
        self._audit.schedule(
            AuditActionType.AGENT_APPLICATION_SUBMITTED,
            resource_type="AgentApplication",
            resource_id=str(row.id),
            actor_id=user_id,
            from_state=AgentApplicationStatus.DRAFT.value,
            to_state=AgentApplicationStatus.PENDING.value,
            ip_address=ip_address,
        )
        return self._to_public_dto(await self._repo.get_by_user_id(user_id))

    # ── Admin actions ──────────────────────────────────────────────

    async def approve(self, application_id: str, admin_id: str) -> AgentApplicationDto:
        row = await self._repo.get_model(application_id)
        if row is None:
            raise ResourceNotFoundException(resource="AgentApplication")
        self._validator.assert_pending(row)

        await self._repo.update(application_id, UpdateAgentApplicationDto(
            status=AgentApplicationStatus.APPROVED,
            reviewed_by_admin_id=admin_id,
            reviewed_at=Utils.datetime_now(),
        ))
        # Add AGENT persona (idempotent).
        await self._user_service.add_persona(row.user_id, UserPersona.AGENT)

        await self._record_security_event(
            user_id=row.user_id,
            type_=SecurityEventType.AGENT_APPLICATION_APPROVED,
            description=f"approved by admin {admin_id}",
        )
        self._audit.schedule(
            AuditActionType.AGENT_APPLICATION_APPROVED,
            resource_type="AgentApplication",
            resource_id=application_id,
            actor_id=admin_id,
            from_state=AgentApplicationStatus.PENDING.value,
            to_state=AgentApplicationStatus.APPROVED.value,
        )
        return self._to_public_dto(await self._repo.get_model(application_id))

    async def reject(self, application_id: str, admin_id: str, reason: str) -> AgentApplicationDto:
        self._validator.assert_rejection_reason(reason)
        row = await self._repo.get_model(application_id)
        if row is None:
            raise ResourceNotFoundException(resource="AgentApplication")
        self._validator.assert_pending(row)

        await self._repo.update(application_id, UpdateAgentApplicationDto(
            status=AgentApplicationStatus.REJECTED,
            reviewed_by_admin_id=admin_id,
            reviewed_at=Utils.datetime_now(),
            rejection_reason=reason,
        ))
        await self._record_security_event(
            user_id=row.user_id,
            type_=SecurityEventType.AGENT_APPLICATION_REJECTED,
            description=f"rejected by admin {admin_id}: {reason[:120]}",
        )
        self._audit.schedule(
            AuditActionType.AGENT_APPLICATION_REJECTED,
            resource_type="AgentApplication",
            resource_id=application_id,
            actor_id=admin_id,
            from_state=AgentApplicationStatus.PENDING.value,
            to_state=AgentApplicationStatus.REJECTED.value,
            meta={"reason": reason},
        )
        return self._to_public_dto(await self._repo.get_model(application_id))

    # ── Helpers ────────────────────────────────────────────────────

    @staticmethod
    def _to_public_dto(row: Optional[AgentApplication]) -> Optional[AgentApplicationDto]:
        if row is None:
            return None
        return AgentApplicationDto(
            id=str(row.id),
            user_id=row.user_id,
            status=AgentApplicationStatus(row.status),
            types=[AgentType(t) for t in (row.types or [])],
            kyc_method=KycMethod(row.kyc_method) if row.kyc_method else None,
            bvn_last4=row.bvn_last4,
            bvn_verified_at=row.bvn_verified_at,
            id_doc_type=IdDocType(row.id_doc_type) if row.id_doc_type else None,
            id_doc_uploaded=bool(row.id_doc_url),
            selfie_uploaded=bool(row.selfie_url),
            selfie_match_score=row.selfie_match_score,
            surveyor_licence_no=row.surveyor_licence_no,
            nba_licence_no=row.nba_licence_no,
            years_of_experience=row.years_of_experience,
            coverage_states=list(row.coverage_states or []),
            coverage_lgas=list(row.coverage_lgas or []),
            bio=row.bio,
            submitted_at=row.submitted_at,
            reviewed_at=row.reviewed_at,
            rejection_reason=row.rejection_reason,
            created_at=row.date_created,
            updated_at=row.date_updated,
        )

    def _to_admin_dto(self, row: AgentApplication, user) -> AdminAgentApplicationDto:
        public = self._to_public_dto(row)
        return AdminAgentApplicationDto(
            **public.model_dump(),
            id_doc_url=row.id_doc_url,
            selfie_url=row.selfie_url,
            surveyor_licence_url=row.surveyor_licence_url,
            nba_licence_url=row.nba_licence_url,
            user_first_name=user.first_name if user else None,
            user_last_name=user.last_name if user else None,
            user_email=user.email if user else None,
        )

    async def _record_security_event(
        self, user_id: str, type_: SecurityEventType, description: str,
    ) -> None:
        # Reuse SessionService's audit writer to keep security events
        # consistent. Best-effort — state change is the source of truth.
        try:
            await self._session_service.record_event(
                type=type_,
                description=description[:255],
                user_id=user_id,
            )
        except Exception:  # pragma: no cover
            logger.warning("Could not record agent application security event", exc_info=True)
