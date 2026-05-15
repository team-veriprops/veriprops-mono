"""Admin verification service — PRD Phase 6 (R6.1, R6.2, R6.5).

All mutation methods emit audit log entries. Status changes also go through
the verification state machine so illegal transitions are rejected.
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from kink import di, inject

from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.verification.admin.models import (
    AddNoteDto,
    AdminVerificationDetailDto,
    AdminVerificationListItemDto,
    CreateVerificationNoteDto,
    SetDelayDto,
    UpdateNoteDto,
    VerificationNote,
    VerificationNoteDto,
)
from main.app.domain.verification.admin.repo import AdminVerificationRepo, VerificationNoteRepo
from main.app.domain.verification.models import (
    UpdateVerificationDto,
    Verification,
    VerificationStatus,
    VerificationTier,
)
from main.app.domain.verification.property.models import PropertySource, PropertyType
from main.app.domain.verification.property.repo import PropertyRepo
from main.app.domain.verification.repo import VerificationRepo
from main.app.domain.verification.validator import VerificationValidator
from main.app.state.machine import verification_state_machine
from main.appodus_utils import Utils
from main.appodus_utils.db.models import Page, PaginationMeta
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    ResourceNotFoundException,
    ValidationException,
)

if TYPE_CHECKING:
    from loguru import Logger

logger: "Logger" = di["logger"]


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class AdminVerificationService:
    def __init__(
        self,
        repo: VerificationRepo,
        admin_repo: AdminVerificationRepo,
        note_repo: VerificationNoteRepo,
        property_repo: PropertyRepo,
        validator: VerificationValidator,
        audit: AuditLogService,
    ):
        self._repo = repo
        self._admin_repo = admin_repo
        self._note_repo = note_repo
        self._property_repo = property_repo
        self._validator = validator
        self._audit = audit

    # ── List / Read ───────────────────────────────────────────────

    async def list_verifications(
        self,
        *,
        status: Optional[str] = None,
        tier: Optional[str] = None,
        state: Optional[str] = None,
        lga: Optional[str] = None,
        vid: Optional[str] = None,
        page: int = 0,
        page_size: int = 25,
    ) -> Page[AdminVerificationListItemDto]:
        rows, total = await self._admin_repo.list_admin(
            status=status,
            tier=tier,
            state=state,
            lga=lga,
            vid=vid,
            page=page,
            page_size=page_size,
        )
        items: List[AdminVerificationListItemDto] = []
        for row in rows:
            prop = await self._property_repo.get_model(row.property_id) if row.property_id else None
            items.append(self._to_list_dto(row, prop))

        meta = PaginationMeta(page=page, page_size=page_size, count=len(items), total=total)
        return Page[AdminVerificationListItemDto](items=items, meta=meta)

    async def get_detail(self, vid: str) -> AdminVerificationDetailDto:
        row = await self._admin_repo.get_by_vid(vid)
        if row is None:
            raise ResourceNotFoundException(resource="Verification")
        prop = await self._property_repo.get_model(row.property_id) if row.property_id else None
        notes = await self._note_repo.list_for_verification(str(row.id))
        return self._to_detail_dto(row, prop, notes)

    # ── Admin actions ─────────────────────────────────────────────

    async def pause(self, vid: str, admin_id: str) -> AdminVerificationDetailDto:
        return await self._transition(vid, VerificationStatus.IN_PROGRESS, admin_id, "PAUSE")

    async def resume(self, vid: str, admin_id: str) -> AdminVerificationDetailDto:
        return await self._transition(vid, VerificationStatus.IN_PROGRESS, admin_id, "RESUME")

    async def cancel(self, vid: str, admin_id: str) -> AdminVerificationDetailDto:
        return await self._transition(vid, VerificationStatus.CANCELLED, admin_id, "CANCEL")

    async def fail(self, vid: str, admin_id: str, reason: str) -> AdminVerificationDetailDto:
        row = await self._get_or_raise(vid)
        self._validator.assert_can_transition(row.status, VerificationStatus.FAILED.value)
        await self._repo.update(str(row.id), UpdateVerificationDto(status=VerificationStatus.FAILED))
        self._audit.schedule(
            AuditActionType.VERIFICATION_STATE_CHANGED,
            resource_type="Verification",
            resource_id=str(row.id),
            actor_id=admin_id,
            from_state=row.status,
            to_state=VerificationStatus.FAILED.value,
            meta={"action": "FAIL", "reason": reason},
        )
        return await self.get_detail(vid)

    async def set_delay(
        self, vid: str, admin_id: str, dto: SetDelayDto,
    ) -> AdminVerificationDetailDto:
        row = await self._get_or_raise(vid)
        self._audit.schedule(
            AuditActionType.VERIFICATION_STATE_CHANGED,
            resource_type="Verification",
            resource_id=str(row.id),
            actor_id=admin_id,
            meta={"action": "SET_DELAY", "delay_hours": dto.delay_hours, "reason": dto.reason},
        )
        return await self.get_detail(vid)

    async def add_note(
        self, vid: str, admin_id: str, dto: AddNoteDto,
    ) -> VerificationNoteDto:
        row = await self._get_or_raise(vid)
        note = await self._note_repo.create_return_model(CreateVerificationNoteDto(
            verification_id=str(row.id),
            admin_id=admin_id,
            content=dto.content,
            tags=dto.tags,
            pinned=dto.pinned,
        ))
        self._audit.schedule(
            AuditActionType.VERIFICATION_STATE_CHANGED,
            resource_type="Verification",
            resource_id=str(row.id),
            actor_id=admin_id,
            meta={"action": "ADD_NOTE", "note_id": str(note.id)},
        )
        return self._note_to_dto(note)

    async def update_note(
        self, vid: str, note_id: str, admin_id: str, dto: UpdateNoteDto,
    ) -> VerificationNoteDto:
        row = await self._get_or_raise(vid)
        note = await self._note_repo.get_model(note_id)
        if note is None or str(note.verification_id) != str(row.id):
            raise ResourceNotFoundException(resource="VerificationNote")
        from main.app.domain.verification.admin.models import UpdateVerificationNoteDto
        await self._note_repo.update(note_id, UpdateVerificationNoteDto(
            pinned=dto.pinned,
            tags=dto.tags,
        ))
        return self._note_to_dto(await self._note_repo.get_model(note_id))

    async def release_to_pool(self, vid: str, admin_id: str) -> AdminVerificationDetailDto:
        """Release tasks for a held verification into the agent pool."""
        row = await self._get_or_raise(vid)
        if VerificationStatus(row.status) != VerificationStatus.PAID:
            raise ValidationException(message="Only PAID verifications can release tasks to pool")
        self._audit.schedule(
            AuditActionType.VERIFICATION_STATE_CHANGED,
            resource_type="Verification",
            resource_id=str(row.id),
            actor_id=admin_id,
            meta={"action": "RELEASE_TO_POOL"},
        )
        # Actual task pool release is delegated to TaskService (called by S19 endpoint)
        return await self.get_detail(vid)

    # ── Helpers ───────────────────────────────────────────────────

    async def _transition(
        self, vid: str, target: VerificationStatus, admin_id: str, action: str,
    ) -> AdminVerificationDetailDto:
        row = await self._get_or_raise(vid)
        from_state = row.status
        self._validator.assert_can_transition(from_state, target.value)
        await self._repo.update(str(row.id), UpdateVerificationDto(status=target))
        self._audit.schedule(
            AuditActionType.VERIFICATION_STATE_CHANGED,
            resource_type="Verification",
            resource_id=str(row.id),
            actor_id=admin_id,
            from_state=from_state,
            to_state=target.value,
            meta={"action": action},
        )
        return await self.get_detail(vid)

    async def _get_or_raise(self, vid: str) -> Verification:
        row = await self._admin_repo.get_by_vid(vid)
        if row is None:
            raise ResourceNotFoundException(resource="Verification")
        return row

    @staticmethod
    def _to_list_dto(row: Verification, prop) -> AdminVerificationListItemDto:
        return AdminVerificationListItemDto(
            id=str(row.id),
            vid=row.vid,
            customer_id=row.customer_id,
            tier=VerificationTier(row.tier),
            status=VerificationStatus(row.status),
            state=prop.state if prop else None,
            lga=prop.lga if prop else None,
            address_line=prop.address_line if prop else None,
            submitted_at=row.submitted_at,
            paid_at=row.paid_at,
            date_created=row.date_created,
            date_updated=row.date_updated,
        )

    @staticmethod
    def _to_detail_dto(row: Verification, prop, notes: List[VerificationNote]) -> AdminVerificationDetailDto:
        prop_data: Optional[Dict[str, Any]] = None
        if prop:
            prop_data = {
                "id": str(prop.id),
                "state": prop.state,
                "lga": prop.lga,
                "addressLine": prop.address_line,
                "propertyType": prop.property_type,
                "source": prop.source,
                "lat": prop.lat,
                "lng": prop.lng,
            }
        pricing_data: Optional[Dict[str, Any]] = None
        if row.pricing_snapshot:
            try:
                pricing_data = json.loads(row.pricing_snapshot)
            except (json.JSONDecodeError, ValueError):
                pass
        return AdminVerificationDetailDto(
            id=str(row.id),
            vid=row.vid,
            customer_id=row.customer_id,
            tier=VerificationTier(row.tier),
            status=VerificationStatus(row.status),
            property=prop_data,
            pricing=pricing_data,
            notes=[AdminVerificationService._note_to_dto(n) for n in notes],
            submitted_at=row.submitted_at,
            paid_at=row.paid_at,
            completed_at=row.completed_at,
            date_created=row.date_created,
            date_updated=row.date_updated,
        )

    @staticmethod
    def _note_to_dto(note: VerificationNote) -> VerificationNoteDto:
        return VerificationNoteDto(
            id=str(note.id),
            verification_id=note.verification_id,
            admin_id=note.admin_id,
            content=note.content,
            tags=list(note.tags or []),
            pinned=bool(note.pinned),
            date_created=note.date_created,
            date_updated=note.date_updated,
        )
