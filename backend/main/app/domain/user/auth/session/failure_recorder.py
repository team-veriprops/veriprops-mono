"""What a failed sign-in or verification leaves behind, although the request then fails.

A failed attempt is recorded and then answered with an error. Recorded in the request's own
transaction, the error's rollback erased the record: the failure counter never grew, the
account never locked, and the security log never showed the attempt. These writes therefore
commit on their own (`INDEPENDENT`).

Success-path events (account created, password changed, OAuth linked) are not written here.
They belong in the transaction of the change they describe, and should roll back with it.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

from kink import inject

from main.app.config.settings import settings
from main.app.domain.user.auth.session.models import CreateSecurityEventDto, SecurityEventType
from main.app.domain.user.auth.session.repo import SecurityEventRepo
from main.app.domain.user.repo import UserRepo
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import TransactionSessionPolicy, transactional


def security_event(
        type: SecurityEventType,
        description: str,
        *,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        approx_location: Optional[str] = None,
        device: Optional[str] = None,
        device_fingerprint: Optional[str] = None,
) -> CreateSecurityEventDto:
    """The security-log row for an event, stamped now."""
    return CreateSecurityEventDto(
        user_id=user_id,
        type=type,
        description=description,
        ip_address=ip_address,
        approx_location=approx_location,
        device=device,
        device_fingerprint=device_fingerprint,
        occurred_at=Utils.datetime_now(),
    )


@inject
@decorate_all_methods(
    transactional(session_policy=TransactionSessionPolicy.INDEPENDENT),
    exclude=["__init__"], exclude_startswith=["_"],
)
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class AuthFailureRecorder:
    def __init__(self, user_repo: UserRepo, event_repo: SecurityEventRepo):
        self._user_repo = user_repo
        self._event_repo = event_repo

    async def record_event(
            self,
            type: SecurityEventType,
            description: str,
            *,
            user_id: Optional[str] = None,
            ip_address: Optional[str] = None,
            device_fingerprint: Optional[str] = None,
    ) -> None:
        """Log a failed attempt that has no counter of its own (unknown email, locked or
        suspended account, wrong OTP)."""
        await self._event_repo.create(security_event(
            type, description,
            user_id=user_id, ip_address=ip_address, device_fingerprint=device_fingerprint,
        ))

    async def record_failed_login(
            self,
            user_id: str,
            *,
            ip_address: Optional[str] = None,
            device_fingerprint: Optional[str] = None,
    ) -> int:
        """Count a wrong password for *user_id*, lock the account at the threshold, and log it.

        Two attempts before the lockout (5 of 7 by default) log a WARNING, so the Security
        Activity Log can show a brute-force attempt while it is still in progress.
        """
        count = await self._user_repo.increment_failed_login(user_id)
        threshold = settings.AUTH_LOCKOUT_THRESHOLD
        warn_at = max(1, threshold - 2)

        if count >= threshold:
            until = Utils.datetime_now() + timedelta(minutes=settings.AUTH_LOCKOUT_MINUTES)
            await self._user_repo.lock_until(user_id, until)
            event = security_event(
                SecurityEventType.ACCOUNT_LOCKED,
                f"Account locked for {settings.AUTH_LOCKOUT_MINUTES} minutes",
                user_id=user_id, ip_address=ip_address,
            )
        elif count >= warn_at:
            event = security_event(
                SecurityEventType.LOGIN_FAILURE_WARNING,
                f"Repeated invalid credentials ({count}/{threshold})",
                user_id=user_id, ip_address=ip_address, device_fingerprint=device_fingerprint,
            )
        else:
            event = security_event(
                SecurityEventType.LOGIN_FAILURE,
                "Invalid credentials",
                user_id=user_id, ip_address=ip_address, device_fingerprint=device_fingerprint,
            )
        await self._event_repo.create(event)
        return count
