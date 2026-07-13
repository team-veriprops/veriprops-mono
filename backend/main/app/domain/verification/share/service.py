"""Report sharing service (PRD §13.1, §13.2).

Owns the four sharing modes and the unauthenticated public lookup:

- **Public visibility** (VID lookup): toggles ``verification.public_lookup_enabled``.
- **Link / named shares**: creates tokenised, revocable, time-limited ``VerificationShare``
  rows. ``LINK_SUMMARY`` returns the public summary; ``NAMED_FULL`` emails a link and returns
  the full report after a one-time disclaimer acknowledgement.

Public reads never leak beyond the §13.1 allow-list (VID, verified badge, trust *band*, tier,
report date, property type, state & LGA, version). The numeric score, full address, and
agent/owner identities are never exposed on a public surface.
"""
from __future__ import annotations

from datetime import timedelta
from typing import List, Optional

from kink import inject

from main.app.config.settings import settings
from main.app.core.state.status import ShareType, VerificationStatus, VerificationTier
from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.message.verification_messages import VerificationMessages
from main.app.domain.property.repo import PropertyRepo
from main.app.domain.verification.models import UpdateVerificationDto
from main.app.domain.verification.report.content import trust_band
from main.app.domain.verification.report.customer_service import CustomerReportService
from main.app.domain.verification.report.service import ReportService
from main.app.domain.verification.repo import VerificationRepo
from main.app.domain.verification.service import VerificationService
from main.app.domain.verification.share.models import (
    CreateShareRequestDto,
    CreateVerificationShareDto,
    PublicLookupState,
    PublicSummaryDto,
    ShareDto,
    SharedReportDto,
    UpdateVerificationShareDto,
    VerificationShare,
)
from main.app.domain.verification.share.repo import VerificationShareRepo
from main.app.domain.system_config.models import ConfigKey
from main.app.domain.system_config.service import ConfigService
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    ResourceNotFoundException,
    ValidationException,
)

_PRIVATE_MESSAGE = "Public sharing is not enabled for this verification."
_IN_PROGRESS_MESSAGE = "This verification is still in progress."
_DISPUTED_MESSAGE = "This verification is under dispute review."
_NOT_FOUND_MESSAGE = "No verification was found for this reference."


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class ShareService:
    def __init__(
        self,
        share_repo: VerificationShareRepo,
        verification_repo: VerificationRepo,
        verification_service: VerificationService,
        report_service: ReportService,
        customer_report_service: CustomerReportService,
        property_repo: PropertyRepo,
        verification_messages: VerificationMessages,
        audit_service: AuditLogService,
        config_service: ConfigService,
    ):
        self._share_repo = share_repo
        self._verification_repo = verification_repo
        self._verifications = verification_service
        self._share_reports = report_service
        self._customer_report = customer_report_service
        self._properties = property_repo
        self._messages = verification_messages
        self._audit = audit_service
        self._config = config_service

    # ── Customer share management (§13.2) ─────────────────────────

    async def set_public_visibility(
        self, verification_id: str, customer_id: str, enabled: bool
    ) -> bool:
        """Toggle PUBLIC mode — anyone with the VID sees the summary (§13.1)."""
        v = await self._verifications.get_owned(verification_id, customer_id)
        await self._require_released(verification_id)
        await self._verification_repo.update(
            v.id, UpdateVerificationDto(public_lookup_enabled=enabled)
        )
        self._audit.schedule(
            action=AuditActionType.VERIFICATION_STATE_CHANGED,
            resource_type="verification", resource_id=v.id, actor_id=customer_id,
            details={"event": "public_lookup", "enabled": enabled},
        )
        return enabled

    async def create_share(
        self, verification_id: str, customer_id: str, req: CreateShareRequestDto
    ) -> ShareDto:
        """Create a link-only or named-recipient share (§13.2). A named share emails the
        recipient a link to the full report."""
        v = await self._verifications.get_owned(verification_id, customer_id)
        await self._require_released(verification_id)

        if req.share_type == ShareType.NAMED_FULL and not (req.recipient_email or "").strip():
            raise ValidationException(message="A recipient email is required for a named share.")

        share = await self._share_repo.create_return_model(CreateVerificationShareDto(
            verification_id=Utils.uuid_to_hex(v.id),
            share_type=req.share_type,
            token=Utils.random_str(36),
            recipient_email=(req.recipient_email or None) if req.share_type == ShareType.NAMED_FULL else None,
        ))
        default_expiry_days = await self._config.get_int(ConfigKey.SHARE_LINK_DEFAULT_EXPIRY_DAYS)
        days = req.expires_in_days if req.expires_in_days and req.expires_in_days > 0 else default_expiry_days
        share.expires_at = Utils.datetime_now() + timedelta(days=days)

        self._audit.schedule(
            action=AuditActionType.VERIFICATION_STATE_CHANGED,
            resource_type="verification_share", resource_id=share.id, actor_id=customer_id,
            details={"event": "share_created", "type": req.share_type.value,
                     "verification_id": verification_id},
        )
        if share.share_type == ShareType.NAMED_FULL and share.recipient_email:
            await self._email_named_share(share, v.vid)
        return self._to_dto(share)

    async def list_shares(self, verification_id: str, customer_id: str) -> List[ShareDto]:
        v = await self._verifications.get_owned(verification_id, customer_id)
        rows = await self._share_repo.list_for_verification(Utils.uuid_to_hex(v.id))
        return [self._to_dto(r) for r in rows]

    async def revoke_share(self, verification_id: str, share_id: str, customer_id: str) -> ShareDto:
        """Revoke a share — the token is invalid immediately (§13.3)."""
        v = await self._verifications.get_owned(verification_id, customer_id)
        share = await self._share_repo.get_model(share_id)
        if share is None or share.verification_id != Utils.uuid_to_hex(v.id):
            raise ResourceNotFoundException(resource="share")
        if share.revoked_at is None:
            await self._set_revoked(share.id)
            self._audit.schedule(
                action=AuditActionType.VERIFICATION_STATE_CHANGED,
                resource_type="verification_share", resource_id=share.id, actor_id=customer_id,
                details={"event": "share_revoked", "verification_id": verification_id},
            )
        return self._to_dto(await self._share_repo.get_model(share.id))

    # ── Public lookup (§13.1) — unauthenticated ───────────────────

    async def public_lookup(self, vid: str) -> PublicSummaryDto:
        """VID lookup: summary only when the report is COMPLETED and public, else a state
        marker. Leaks nothing beyond the §13.1 allow-list."""
        verification = await self._verification_repo.get_by_vid(vid)
        if verification is None:
            return PublicSummaryDto(state=PublicLookupState.NOT_FOUND, message=_NOT_FOUND_MESSAGE)
        state = self._public_state(verification.status)
        if state != PublicLookupState.SHARED:
            return PublicSummaryDto(state=state, message=self._state_message(state))
        if not bool(verification.public_lookup_enabled):
            return PublicSummaryDto(state=PublicLookupState.PRIVATE, message=_PRIVATE_MESSAGE)
        return await self._build_summary(verification)

    async def resolve_shared(self, token: str) -> SharedReportDto:
        """Tokenised share view: summary for a link, full report for a named recipient once
        the disclaimer is acknowledged. Invalid / revoked / expired → NOT_FOUND (§13.3)."""
        share = await self._valid_share(token)
        if share is None:
            return SharedReportDto(state=PublicLookupState.NOT_FOUND, message=None)
        verification = await self._verification_repo.get_model(share.verification_id)
        if verification is None:
            return SharedReportDto(state=PublicLookupState.NOT_FOUND)
        state = self._public_state(verification.status)
        if state != PublicLookupState.SHARED:
            return SharedReportDto(state=state, share_type=ShareType(share.share_type))
        if share.first_viewed_at is None:
            await self._set_first_viewed(share.id)

        share_type = ShareType(share.share_type)
        if share_type == ShareType.LINK_SUMMARY:
            summary = await self._build_summary(verification)
            return SharedReportDto(state=state, share_type=share_type, summary=summary)

        # NAMED_FULL — full report, gated on the one-time disclaimer acknowledgement (§13.2).
        if share.disclaimer_acked_at is None:
            return SharedReportDto(
                state=state, share_type=share_type, requires_acknowledgement=True,
                summary=await self._build_summary(verification),
            )
        report = await self._customer_report.build_shared_content(verification.id)
        return SharedReportDto(state=state, share_type=share_type, report=report)

    async def acknowledge_shared(self, token: str) -> SharedReportDto:
        """Record the named recipient's one-time disclaimer acknowledgement (§13.2)."""
        share = await self._valid_share(token)
        if share is None or ShareType(share.share_type) != ShareType.NAMED_FULL:
            return SharedReportDto(state=PublicLookupState.NOT_FOUND)
        if share.disclaimer_acked_at is None:
            await self._set_acked(share.id)
        return await self.resolve_shared(token)

    # ── helpers ───────────────────────────────────────────────────

    async def _valid_share(self, token: str) -> Optional[VerificationShare]:
        share = await self._share_repo.get_by_token(token)
        if share is None or share.revoked_at is not None:
            return None
        if share.expires_at is not None and share.expires_at < Utils.datetime_now():
            return None
        return share

    def _public_state(self, status: str) -> PublicLookupState:
        if status == VerificationStatus.COMPLETED.value:
            return PublicLookupState.SHARED
        if status == VerificationStatus.DISPUTED.value:
            return PublicLookupState.DISPUTED
        in_progress = {
            VerificationStatus.PAID.value, VerificationStatus.IN_PROGRESS.value,
            VerificationStatus.UNDER_REVIEW.value, VerificationStatus.SUBMITTED.value,
            VerificationStatus.PAYMENT_PENDING.value,
        }
        if status in in_progress:
            return PublicLookupState.IN_PROGRESS
        return PublicLookupState.NOT_FOUND

    def _state_message(self, state: PublicLookupState) -> Optional[str]:
        return {
            PublicLookupState.PRIVATE: _PRIVATE_MESSAGE,
            PublicLookupState.IN_PROGRESS: _IN_PROGRESS_MESSAGE,
            PublicLookupState.DISPUTED: _DISPUTED_MESSAGE,
            PublicLookupState.NOT_FOUND: _NOT_FOUND_MESSAGE,
        }.get(state)

    async def _build_summary(self, verification) -> PublicSummaryDto:
        # verification.id is a native UUID; report/verification ref columns use the .hex form.
        report = await self._share_reports.get_released(Utils.uuid_to_hex(verification.id))
        band = None
        if report is not None and report.composite_trust_score is not None:
            band, _ = trust_band(report.composite_trust_score)
        property_type = None
        state_region = None
        lga = None
        if verification.property_id:
            prop = await self._properties.get_model(verification.property_id)
            if prop is not None:
                property_type = prop.property_type
                state_region = prop.state
                lga = prop.lga
        return PublicSummaryDto(
            state=PublicLookupState.SHARED,
            vid=verification.vid,
            verified=True,
            trust_band=band,
            tier=VerificationTier(verification.tier) if verification.tier else None,
            property_type=property_type,
            state_region=state_region,
            lga=lga,
            report_version=report.report_version if report else None,
            report_date=report.released_at.date() if report and report.released_at else None,
        )

    async def _require_released(self, verification_id: str) -> None:
        if await self._share_reports.get_released(verification_id) is None:
            raise ValidationException(
                message="Only a verification with a released report can be shared."
            )

    async def _email_named_share(self, share: VerificationShare, vid: str) -> None:
        """Best-effort share invite — a comms failure never breaks share creation."""
        try:
            await self._messages.send_report_share(
                recipient_email=share.recipient_email, vid=vid, share_url=self._share_url(share.token),
            )
        except Exception:  # noqa: BLE001 — share invite is best-effort
            pass

    def _share_url(self, token: str) -> str:
        return f"{settings.PUBLIC_APP_BASE_URL.rstrip('/')}/shared/{token}"

    def _to_dto(self, share: VerificationShare) -> ShareDto:
        active = share.revoked_at is None and (
            share.expires_at is None or share.expires_at >= Utils.datetime_now()
        )
        return ShareDto(
            id=share.id,
            verification_id=share.verification_id,
            share_type=ShareType(share.share_type),
            recipient_email=share.recipient_email,
            token=share.token,
            share_url=self._share_url(share.token),
            expires_at=share.expires_at,
            revoked_at=share.revoked_at,
            first_viewed_at=share.first_viewed_at,
            disclaimer_acked_at=share.disclaimer_acked_at,
            active=active,
            date_created=share.date_created,
        )

    async def _set_revoked(self, share_id: str) -> None:
        share = await self._share_repo.get_model(share_id)
        share.revoked_at = Utils.datetime_now()

    async def _set_first_viewed(self, share_id: str) -> None:
        share = await self._share_repo.get_model(share_id)
        share.first_viewed_at = Utils.datetime_now()

    async def _set_acked(self, share_id: str) -> None:
        share = await self._share_repo.get_model(share_id)
        share.disclaimer_acked_at = Utils.datetime_now()
