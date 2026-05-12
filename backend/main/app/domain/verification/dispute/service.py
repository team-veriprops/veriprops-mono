"""Dispute service — S46."""
from __future__ import annotations

from typing import List, TYPE_CHECKING

from kink import di, inject

from main.app.domain.verification.dispute.models import (
    CreateDisputeDto,
    CreateDisputeResolutionDto,
    DisputeDto,
    DisputeOutcome,
    DisputeResolutionDto,
    DisputeStatus,
    ResolveDisputeDto,
    SearchDisputeDto,
    SubmitDisputeDto,
    UpdateDisputeDto,
)
from main.app.domain.verification.dispute.repo import DisputeRepo, DisputeResolutionRepo
from main.app.domain.verification.dispute.validator import DisputeValidator
from main.app.domain.verification.models import VerificationStatus
from main.app.domain.verification.repo import VerificationRepo
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import ResourceNotFoundException

if TYPE_CHECKING:
    from loguru import Logger

logger: "Logger" = di["logger"]


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class DisputeService:
    def __init__(
        self,
        repo: DisputeRepo,
        resolution_repo: DisputeResolutionRepo,
        ver_repo: VerificationRepo,
        validator: DisputeValidator,
    ):
        self._repo = repo
        self._resolution_repo = resolution_repo
        self._ver_repo = ver_repo
        self._validator = validator

    async def submit(
        self, verification_id: str, customer_id: str, dto: SubmitDisputeDto,
    ) -> DisputeDto:
        ver = await self._ver_repo.get_model(verification_id)
        if ver is None:
            raise ResourceNotFoundException(resource="Verification")
        self._validator.assert_can_dispute(ver.status)
        self._validator.assert_description_length(dto.description)

        now_str = str(Utils.datetime_now())
        row = await self._repo.create(CreateDisputeDto(
            verification_id=verification_id,
            dispute_type=dto.dispute_type,
            description=dto.description,
            status=DisputeStatus.PENDING.value,
            submitted_by=customer_id,
            submitted_at=now_str,
        ))

        # Transition verification to DISPUTED
        from main.app.domain.verification.service import VerificationService
        ver_svc: VerificationService = di[VerificationService]
        await ver_svc.transition(verification_id, VerificationStatus.DISPUTED, actor_id=customer_id)

        # Notify admin
        try:
            from main.app.domain.notification.service import NotificationService
            from main.app.domain.notification.models import NotificationEvent
            notif_svc: NotificationService = di[NotificationService]
            await notif_svc.emit(
                NotificationEvent.DISPUTE_FILED,
                recipient_id=customer_id,  # and admin separately if needed
                context={"vid": ver.vid},
                entity_type="Dispute",
                entity_id=str(row.id),
            )
        except Exception as exc:
            logger.warning(f"Notification emit failed (dispute filed): {exc}")

        return self._to_dto(row)

    async def list_pending(self) -> List[DisputeDto]:
        rows = await self._repo.get_all(SearchDisputeDto(status=DisputeStatus.PENDING.value))
        return [self._to_dto(r) for r in rows]

    async def resolve(
        self, dispute_id: str, admin_id: str, dto: ResolveDisputeDto,
    ) -> DisputeResolutionDto:
        dispute = await self._repo.get_model(dispute_id)
        if dispute is None:
            raise ResourceNotFoundException(resource="Dispute")

        now = Utils.datetime_now()
        now_str = str(now)

        resolution = await self._resolution_repo.create(CreateDisputeResolutionDto(
            dispute_id=dispute_id,
            outcome=dto.outcome.value,
            resolution_note=dto.resolution_note,
            resolved_by=admin_id,
            resolved_at=now_str,
        ))
        await self._repo.update(dispute_id, UpdateDisputeDto(status=DisputeStatus.RESOLVED.value))

        from main.app.domain.verification.service import VerificationService
        ver_svc: VerificationService = di[VerificationService]
        ver = await self._ver_repo.get_model(str(dispute.verification_id))

        if dto.outcome == DisputeOutcome.REJECTED:
            await ver_svc.transition(str(dispute.verification_id), VerificationStatus.COMPLETED, actor_id=admin_id)
        elif dto.outcome == DisputeOutcome.FULL_REFUND:
            await ver_svc.transition(str(dispute.verification_id), VerificationStatus.REFUNDED, actor_id=admin_id)
        elif dto.outcome == DisputeOutcome.PARTIAL_RECHECK:
            await ver_svc.transition(str(dispute.verification_id), VerificationStatus.IN_PROGRESS, actor_id=admin_id)

        # Post resolution note as system message
        try:
            from main.app.domain.thread.service import ThreadService
            from main.app.domain.thread.models import ThreadType
            thread_svc: ThreadService = di[ThreadService]
            note = dto.resolution_note or f"Dispute resolved: {dto.outcome.value}"
            await thread_svc.post_system_message_for_verification(
                str(dispute.verification_id), ThreadType.CUSTOMER_ADMIN, note
            )
        except Exception as exc:
            logger.warning(f"Thread message failed after dispute resolve: {exc}")

        # Notify customer
        try:
            from main.app.domain.notification.service import NotificationService
            from main.app.domain.notification.models import NotificationEvent
            notif_svc: NotificationService = di[NotificationService]
            await notif_svc.emit(
                NotificationEvent.DISPUTE_RESOLVED,
                recipient_id=str(ver.customer_id) if ver else "",
                context={"outcome": dto.outcome.value},
                entity_type="Dispute",
                entity_id=dispute_id,
            )
        except Exception as exc:
            logger.warning(f"Notification emit failed (dispute resolved): {exc}")

        return DisputeResolutionDto(
            id=str(resolution.id),
            dispute_id=dispute_id,
            outcome=DisputeOutcome(resolution.outcome),
            resolution_note=resolution.resolution_note,
            resolved_by=admin_id,
            resolved_at=now_str,
        )

    def _to_dto(self, row) -> DisputeDto:
        return DisputeDto(
            id=str(row.id),
            verification_id=str(row.verification_id),
            dispute_type=row.dispute_type,
            description=row.description,
            status=DisputeStatus(row.status),
            submitted_by=str(row.submitted_by),
            submitted_at=str(row.submitted_at),
            date_created=str(row.date_created),
        )
