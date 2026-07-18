"""Admin user-management service (PRD §4.2): directory, detail, suspend/reactivate,
forced password reset, trust-status override.

Suspension is whole-account (distinct from §2.4 agent role-level credential suspension):
it revokes every device session immediately, and ``SessionService.login`` /
``issue_session_cookies`` refuse a SUSPENDED account, so live access dies within the
access-token TTL. Every action is audit-logged and surfaced on the admin action log.
"""
from __future__ import annotations

from typing import Optional

from kink import inject

from main.app.core.events import DomainEvent, EventType, publish_domain_event
from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.payment.repo import PaymentRepo
from main.app.domain.user.admin_users.models import (
    AdminUserDetailDto,
    AdminUserSummaryDto,
    ForcedPasswordResetDto,
)
from main.app.domain.user.auth.service import AuthService
from main.app.domain.user.auth.session.models import (
    SecurityEventDto,
    SecurityEventType,
    UserPersona,
    UserType,
)
from main.app.domain.user.auth.session.service import SessionService
from main.app.domain.user.models import AccountStatus, AdminSubRole, TrustStatus, User
from main.app.domain.user.repo import UserRepo
from main.app.domain.user.service import UserService
from main.app.domain.verification.repo import VerificationRepo
from main.appodus_utils import Utils
from main.appodus_utils.db.db_utils import DbUtils
from main.appodus_utils.db.models import Page
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import ValidationException

_RESOURCE_TYPE_USER = "user"
_RECENT_SECURITY_EVENTS_LIMIT = 10


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class AdminUsersService:
    def __init__(
        self,
        user_repo: UserRepo,
        user_service: UserService,
        session_service: SessionService,
        auth_service: AuthService,
        audit_service: AuditLogService,
        verification_repo: VerificationRepo,
        payment_repo: PaymentRepo,
    ):
        self._user_repo = user_repo
        self._user_service = user_service
        self._session_service = session_service
        self._auth_service = auth_service
        self._audit_service = audit_service
        self._verification_repo = verification_repo
        self._payment_repo = payment_repo

    # ── Directory ─────────────────────────────────────────────────
    async def list_users(
        self,
        page: int = 0,
        page_size: int = 10,
        query: Optional[str] = None,
        persona: Optional[str] = None,
        user_type: Optional[str] = None,
        trust_status: Optional[str] = None,
        account_status: Optional[str] = None,
    ) -> Page[AdminUserSummaryDto]:
        rows, total = await self._user_repo.page_users(
            offset=page * page_size,
            limit=page_size,
            query=query,
            persona=persona,
            user_type=user_type,
            trust_status=trust_status,
            account_status=account_status,
        )
        items = [self._to_summary(u) for u in rows]
        return DbUtils.build_page(items, total=total, page=page, page_size=page_size)

    async def get_user_detail(self, user_id: str) -> AdminUserDetailDto:
        user = await self._user_service.get_user_model(user_id)
        uid = str(user.id)
        verification_counts = await self._verification_repo.count_by_status_for_customer(uid)
        payments_count = await self._payment_repo.count_for_customer(uid)
        events = await self._session_service.list_recent_events(
            uid, limit=_RECENT_SECURITY_EVENTS_LIMIT
        )
        summary = self._to_summary(user)
        return AdminUserDetailDto(
            **summary.model_dump(),
            first_name=user.first_name,
            last_name=user.last_name,
            phone_country_code=user.phone_country_code,
            phone_verified=bool(user.phone_verified),
            country_of_residence=user.country_of_residence,
            timezone=user.timezone,
            preferred_currency=user.preferred_currency,
            credit_balance_kobo=int(user.credit_balance_kobo or 0),
            referred_by=user.referred_by,
            locked_until=user.locked_until,
            suspended_at=user.suspended_at,
            suspension_reason=user.suspension_reason,
            suspended_by=user.suspended_by,
            verification_counts=verification_counts,
            verifications_total=sum(verification_counts.values()),
            payments_count=payments_count,
            recent_security_events=[self._to_security_event_dto(e) for e in events],
        )

    # ── Account actions ───────────────────────────────────────────
    async def suspend(self, user_id: str, reason: str, admin_id: str) -> None:
        if user_id == admin_id:
            raise ValidationException(message="You cannot suspend your own account.")
        user = await self._user_service.get_user_model(user_id)
        if user.user_type == UserType.ADMIN.value:
            raise ValidationException(
                message="Admin accounts are managed via Admin Team deactivation, not suspension."
            )
        if user.account_status == AccountStatus.SUSPENDED.value:
            raise ValidationException(message="This account is already suspended.")

        uid = str(user.id)
        await self._user_repo.suspend_user(
            user_id, reason=reason, admin_id=admin_id, at=Utils.datetime_now()
        )
        # Kill live access: refresh dies immediately; access tokens die at their TTL.
        await self._session_service.revoke_all_devices_for_user(uid)
        await self._session_service.record_event(
            SecurityEventType.ACCOUNT_SUSPENDED,
            "Account suspended by an administrator",
            user_id=uid,
        )
        self._audit_service.schedule(
            action=AuditActionType.USER_SUSPENDED,
            resource_type=_RESOURCE_TYPE_USER,
            resource_id=user_id,
            actor_id=admin_id,
            from_state=AccountStatus.ACTIVE.value,
            to_state=AccountStatus.SUSPENDED.value,
            details={"reason": reason},
        )
        await publish_domain_event(DomainEvent(
            type=EventType.ACCOUNT_SUSPENDED,
            recipient_user_ids=(uid,),
        ))

    async def reactivate(self, user_id: str, admin_id: str) -> None:
        user = await self._user_service.get_user_model(user_id)
        if user.account_status != AccountStatus.SUSPENDED.value:
            raise ValidationException(message="This account is not suspended.")

        uid = str(user.id)
        await self._user_repo.reactivate_user(user_id)
        await self._session_service.record_event(
            SecurityEventType.ACCOUNT_REACTIVATED,
            "Account reactivated by an administrator",
            user_id=uid,
        )
        self._audit_service.schedule(
            action=AuditActionType.USER_REACTIVATED,
            resource_type=_RESOURCE_TYPE_USER,
            resource_id=user_id,
            actor_id=admin_id,
            from_state=AccountStatus.SUSPENDED.value,
            to_state=AccountStatus.ACTIVE.value,
        )
        await publish_domain_event(DomainEvent(
            type=EventType.ACCOUNT_REACTIVATED,
            recipient_user_ids=(uid,),
        ))

    async def force_password_reset(
        self, user_id: str, admin_id: str
    ) -> Optional[ForcedPasswordResetDto]:
        user = await self._user_service.get_user_model(user_id)
        if user.account_status == AccountStatus.SUSPENDED.value:
            raise ValidationException(
                message="Reactivate the account before forcing a password reset."
            )

        uid = str(user.id)
        issued = await self._auth_service.request_password_reset(user.email)
        if not issued:
            return None
        raw_token, full_name = issued
        # Existing sessions must not survive a forced credential rotation.
        await self._session_service.revoke_all_devices_for_user(uid)
        self._audit_service.schedule(
            action=AuditActionType.PASSWORD_RESET_FORCED,
            resource_type=_RESOURCE_TYPE_USER,
            resource_id=user_id,
            actor_id=admin_id,
        )
        return ForcedPasswordResetDto(raw_token=raw_token, email=user.email, full_name=full_name)

    async def set_trust_status(
        self, user_id: str, trust_status: TrustStatus, admin_id: str
    ) -> None:
        user = await self._user_service.get_user_model(user_id)
        if user.trust_status == trust_status.value:
            raise ValidationException(
                message=f"This account's trust status is already {trust_status.value}."
            )
        from_status = user.trust_status
        await self._user_service.set_trust_status(user_id, trust_status)
        self._audit_service.schedule(
            action=AuditActionType.TRUST_STATUS_CHANGED,
            resource_type=_RESOURCE_TYPE_USER,
            resource_id=user_id,
            actor_id=admin_id,
            from_state=from_status,
            to_state=trust_status.value,
        )

    # ── Mapping helpers ───────────────────────────────────────────
    @staticmethod
    def _to_summary(user: User) -> AdminUserSummaryDto:
        return AdminUserSummaryDto(
            id=user.id,
            name=f"{user.first_name} {user.last_name}".strip(),
            email=user.email,
            email_verified=bool(user.email_verified),
            phone=user.phone,
            phone_dial_code=user.phone_dial_code,
            user_type=UserType(user.user_type),
            personas=[UserPersona(p) for p in (user.personas or [])],
            admin_sub_role=AdminSubRole(user.admin_sub_role) if user.admin_sub_role else None,
            trust_status=TrustStatus(user.trust_status),
            account_status=AccountStatus(user.account_status or AccountStatus.ACTIVE.value),
            avatar_url=user.avatar_url,
            date_created=user.date_created,
        )

    @staticmethod
    def _to_security_event_dto(event) -> SecurityEventDto:
        return SecurityEventDto(
            id=str(event.id),
            type=event.type,
            description=event.description,
            ip_address=event.ip_address,
            approx_location=event.approx_location,
            device=event.device,
            occurred_at=event.occurred_at,
        )
