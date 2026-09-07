"""Per-case delegate endpoints (PRD §26.4.5, WA-26).

URL shape: /verifications/{verification_id}/delegates — session-authenticated, and every
handler proves ownership of the case through `CaseDelegateService`, which gates on
`VerificationService.get_owned`. The case id comes from the path; who may act on it comes
from the session. Neither is taken from a body.

Authorizing sends an OTP, so that route carries the same `RateLimiter` as the other
code-issuing endpoints: the OTP service caps resends per number, and this caps the attempt
rate per client.
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from kink import di
from libre_fastapi_jwt import AuthJWT

from main.app.domain.verification.delegate.models import (
    AuthorizeCaseDelegateDto,
    CaseDelegateChallengeDto,
    CaseDelegateDto,
    ConfirmCaseDelegateDto,
)
from main.app.domain.verification.delegate.service import CaseDelegateService
from main.appodus_utils.common.rate_limit import RateLimiter
from main.appodus_utils.db.models import SuccessResponse

delegate_router = APIRouter(prefix="/verifications", tags=["Case Delegates"])
delegate_service: CaseDelegateService = di[CaseDelegateService]

_authorize_rate_limit = RateLimiter(scope="case_delegate_authorize", limit=10, window_seconds=300)


@delegate_router.get(
    "/{verification_id}/delegates", response_model=SuccessResponse[List[CaseDelegateDto]]
)
async def list_delegates(verification_id: str, authorize: AuthJWT = Depends()):
    """This case's delegate — a list of at most one, so the shape survives §26.9's
    multiple-delegate enhancement without a contract change."""
    await authorize.jwt_required()
    delegates = await delegate_service.list_for_case(
        verification_id, str(authorize.get_jwt_subject())
    )
    return SuccessResponse[List[CaseDelegateDto]](data=delegates)


@delegate_router.post(
    "/{verification_id}/delegates", response_model=SuccessResponse[CaseDelegateChallengeDto]
)
async def authorize_delegate(
    verification_id: str,
    req: AuthorizeCaseDelegateDto,
    authorize: AuthJWT = Depends(),
    _: None = Depends(_authorize_rate_limit),
):
    """Nominate a delegate and send a code to their number. Nothing is visible yet."""
    await authorize.jwt_required()
    challenge = await delegate_service.authorize(
        verification_id, str(authorize.get_jwt_subject()), req.name, req.phone_e164
    )
    return SuccessResponse[CaseDelegateChallengeDto](data=challenge)


@delegate_router.post(
    "/{verification_id}/delegates/confirm", response_model=SuccessResponse[CaseDelegateDto]
)
async def confirm_delegate(
    verification_id: str, req: ConfirmCaseDelegateDto, authorize: AuthJWT = Depends()
):
    """Confirm the code the delegate received. Their visibility begins here."""
    await authorize.jwt_required()
    delegate = await delegate_service.confirm(
        verification_id, str(authorize.get_jwt_subject()), req.code
    )
    return SuccessResponse[CaseDelegateDto](data=delegate)


@delegate_router.post(
    "/{verification_id}/delegates/revoke", response_model=SuccessResponse[dict]
)
async def revoke_delegate(verification_id: str, authorize: AuthJWT = Depends()):
    """End the delegation. Effective on the next event (§26.4.5)."""
    await authorize.jwt_required()
    await delegate_service.revoke(verification_id, str(authorize.get_jwt_subject()))
    return SuccessResponse[dict](data={"revoked": True})
