"""Verification service.

Owns the wizard draft cycle and forward-only state transitions for the global
verification entity. Property creation is folded in here on submission.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

import json
import secrets
from datetime import datetime
from typing import Any, Dict, List, Optional

from kink import di, inject

from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.user.auth.consent.models import (
    ConsentDocumentType,
)
from main.app.domain.user.auth.consent.service import ConsentService
from main.app.domain.verification.models import (
    ConsentRecordDto,
    CreateVerificationDto,
    PricingSnapshotDto,
    SearchVerificationDto,
    UpdateVerificationDto,
    Verification,
    VerificationDto,
    VerificationStatus,
    VerificationTier,
    WizardStepDto,
)
from main.app.domain.verification.pricing.service import PricingService
from main.app.domain.verification.property.models import (
    CreatePropertyDto,
    PropertyDto,
    PropertySource,
    PropertyType,
)
from main.app.domain.verification.property.repo import PropertyRepo
from main.app.domain.verification.repo import VerificationRepo
from main.app.domain.verification.state_machine import verification_state_machine
from main.app.domain.verification.validator import VerificationValidator
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    ResourceNotFoundException,
    ValidationException,
)

logger: Logger = di["logger"]


# 5 verification consent document types from PRD §5.3.
VERIFICATION_CONSENT_TYPES = (
    ConsentDocumentType.VERIFICATION_DISCLAIMER,
    ConsentDocumentType.FINDINGS_OPINION_ACK,
    ConsentDocumentType.JURISDICTION_PLATFORM_ONLY,
    ConsentDocumentType.COMMUNICATION_RECORDING,
    ConsentDocumentType.REFUND_POLICY,
)


def _generate_vid() -> str:
    """Format: VP-YYYY-XXXXXX (6 random uppercase chars)."""
    year = datetime.utcnow().year
    suffix = secrets.token_hex(3).upper()
    return f"VP-{year}-{suffix}"


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class VerificationService:
    def __init__(
        self,
        repo: VerificationRepo,
        property_repo: PropertyRepo,
        validator: VerificationValidator,
        pricing_service: PricingService,
        consent_service: ConsentService,
        audit: AuditLogService,
    ):
        self._repo = repo
        self._property_repo = property_repo
        self._validator = validator
        self._pricing = pricing_service
        self._consent_service = consent_service
        self._audit = audit

    # ── Reads ─────────────────────────────────────────────────────

    async def get(self, verification_id: str, customer_id: str) -> VerificationDto:
        row = await self._repo.get_model(verification_id)
        if row is None:
            raise ResourceNotFoundException(resource="Verification")
        self._validator.assert_owner(row, customer_id)
        return await self._to_dto(row)

    async def get_active_draft(self, customer_id: str) -> Optional[VerificationDto]:
        row = await self._repo.get_active_draft_for_customer(customer_id)
        return await self._to_dto(row) if row else None

    async def list_for_customer(
        self, customer_id: str, page: int = 1, page_size: int = 20,
    ):
        search = SearchVerificationDto(page=page, page_size=page_size, customer_id=customer_id)
        return await self._repo.get_page(search)

    # ── Wizard ────────────────────────────────────────────────────

    async def create_or_resume_draft(self, customer_id: str) -> VerificationDto:
        row = await self._repo.get_active_draft_for_customer(customer_id)
        if row is None:
            vid = _generate_vid()
            await self._repo.create(CreateVerificationDto(
                vid=vid,
                customer_id=customer_id,
                tier=VerificationTier.STANDARD,
                status=VerificationStatus.DRAFT,
                draft_step=0,
            ))
            row = await self._repo.get_by_vid(vid)
        return await self._to_dto(row)

    async def update_draft_step(
        self, customer_id: str, verification_id: str, dto: WizardStepDto,
    ) -> VerificationDto:
        row = await self._repo.get_model(verification_id)
        if row is None:
            raise ResourceNotFoundException(resource="Verification")
        self._validator.assert_owner(row, customer_id)
        self._validator.assert_draft(row)

        # Merge incoming payload into the persisted draft.
        existing = self._decode_payload(row.draft_payload)
        existing.update(dto.payload or {})

        await self._repo.update(verification_id, UpdateVerificationDto(
            draft_step=dto.step,
            draft_payload=json.dumps(existing),
        ))
        return await self._to_dto(await self._repo.get_model(verification_id))

    async def select_tier(
        self, customer_id: str, verification_id: str, tier: VerificationTier, currency: str,
    ) -> VerificationDto:
        row = await self._repo.get_model(verification_id)
        if row is None:
            raise ResourceNotFoundException(resource="Verification")
        self._validator.assert_owner(row, customer_id)
        self._validator.assert_draft(row)

        snapshot = self._pricing.quote(tier, currency)
        snapshot = self._pricing.lock(snapshot)
        await self._repo.update(verification_id, UpdateVerificationDto(
            tier=tier,
            pricing_snapshot=snapshot.model_dump_json(by_alias=True),
        ))
        return await self._to_dto(await self._repo.get_model(verification_id))

    async def submit(
        self,
        customer_id: str,
        verification_id: str,
        consents: List[ConsentRecordDto],
        ip_address: Optional[str] = None,
        device_fingerprint: Optional[str] = None,
    ) -> VerificationDto:
        row = await self._repo.get_model(verification_id)
        if row is None:
            raise ResourceNotFoundException(resource="Verification")
        self._validator.assert_owner(row, customer_id)
        self._validator.assert_draft(row)

        payload = self._decode_payload(row.draft_payload)
        self._validator.assert_property_filled(payload)
        self._validator.assert_can_transition(row.status, VerificationStatus.SUBMITTED.value)

        # Validate that all 5 consents were collected.
        provided_types = {c.document_type for c in consents}
        required_types = {t.value for t in VERIFICATION_CONSENT_TYPES}
        missing = required_types - provided_types
        if missing:
            raise ValidationException(
                message=f"Missing required consents: {', '.join(sorted(missing))}",
            )

        property_id = await self._materialise_property(payload)

        for consent in consents:
            await self._consent_service.record_user_consent(
                user_id=customer_id,
                document_type=ConsentDocumentType(consent.document_type),
                consent_version=consent.consent_version,
                ip_address=ip_address,
                device_fingerprint=device_fingerprint,
            )

        await self._repo.update(verification_id, UpdateVerificationDto(
            status=VerificationStatus.SUBMITTED,
            property_id=property_id,
            submitted_at=Utils.datetime_now(),
        ))
        self._audit.schedule(
            AuditActionType.VERIFICATION_SUBMITTED,
            resource_type="Verification",
            resource_id=verification_id,
            actor_id=customer_id,
            from_state=VerificationStatus.DRAFT.value,
            to_state=VerificationStatus.SUBMITTED.value,
            ip_address=ip_address,
        )
        return await self._to_dto(await self._repo.get_model(verification_id))

    async def transition(
        self, verification_id: str, target: VerificationStatus,
        actor_id: Optional[str] = None,
    ) -> VerificationDto:
        """Internal-only. Used by PaymentService and admin actions."""
        row = await self._repo.get_model(verification_id)
        if row is None:
            raise ResourceNotFoundException(resource="Verification")
        from_state = row.status
        self._validator.assert_can_transition(row.status, target.value)
        update = UpdateVerificationDto(status=target)
        if target == VerificationStatus.PAID:
            update.paid_at = Utils.datetime_now()
        elif target == VerificationStatus.COMPLETED:
            update.completed_at = Utils.datetime_now()
        await self._repo.update(verification_id, update)
        self._audit.schedule(
            AuditActionType.VERIFICATION_STATE_CHANGED,
            resource_type="Verification",
            resource_id=verification_id,
            actor_id=actor_id,
            from_state=from_state,
            to_state=target.value,
        )
        return await self._to_dto(await self._repo.get_model(verification_id))

    # ── Helpers ───────────────────────────────────────────────────

    async def _materialise_property(self, payload: Dict[str, Any]) -> str:
        try:
            create_dto = CreatePropertyDto(
                source=PropertySource(payload.get("source", "MANUAL")),
                source_url=payload.get("sourceUrl"),
                property_type=PropertyType(payload["propertyType"]),
                state=str(payload["state"]).upper(),
                lga=payload.get("lga"),
                address_line=payload.get("addressLine"),
                lat=payload.get("lat"),
                lng=payload.get("lng"),
                landmark_description=payload.get("landmarkDescription"),
                details=json.dumps(payload.get("details") or {}),
                documents=list(payload.get("documents") or []),
                seller_info=json.dumps(payload.get("sellerInfo") or {}),
            )
        except (KeyError, ValueError) as exc:
            raise ValidationException(message=f"Property data invalid: {exc}")
        created = await self._property_repo.create_return_model(create_dto)
        return str(created.id)

    @staticmethod
    def _decode_payload(raw: Optional[str]) -> Dict[str, Any]:
        if not raw:
            return {}
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Discarding malformed draft payload")
            return {}
        return decoded if isinstance(decoded, dict) else {}

    async def _to_dto(self, row: Optional[Verification]) -> Optional[VerificationDto]:
        if row is None:
            return None
        property_dto: Optional[PropertyDto] = None
        if row.property_id:
            prop = await self._property_repo.get_model(row.property_id)
            if prop:
                property_dto = PropertyDto(
                    id=str(prop.id),
                    source=PropertySource(prop.source),
                    property_type=PropertyType(prop.property_type),
                    state=prop.state,
                    lga=prop.lga,
                    address_line=prop.address_line,
                    lat=prop.lat,
                    lng=prop.lng,
                    landmark_description=prop.landmark_description,
                    details=self._decode_payload(prop.details),
                    documents=list(prop.documents or []),
                    seller_info=self._decode_payload(prop.seller_info),
                )
        pricing: Optional[PricingSnapshotDto] = None
        if row.pricing_snapshot:
            try:
                pricing = PricingSnapshotDto.model_validate(json.loads(row.pricing_snapshot))
            except (json.JSONDecodeError, ValueError):
                logger.warning("Discarding malformed pricing snapshot for verification {}", row.id)

        return VerificationDto(
            id=str(row.id),
            vid=row.vid,
            customer_id=row.customer_id,
            tier=VerificationTier(row.tier),
            status=VerificationStatus(row.status),
            property=property_dto,
            pricing=pricing,
            submitted_at=row.submitted_at,
            paid_at=row.paid_at,
            completed_at=row.completed_at,
            created_at=row.date_created,
            updated_at=row.date_updated,
            draft_step=row.draft_step or 0,
            draft_payload=self._decode_payload(row.draft_payload),
        )
