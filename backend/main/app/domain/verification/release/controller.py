"""Release endpoints — S31 (admin releases report or marks verification FAILED)."""
from __future__ import annotations

from fastapi import Depends

from main.app.domain.verification.release.models import FailReleaseDto, ReleaseDto
from main.app.domain.verification.release.service import ReleaseService
from main.appodus_utils.auth.jwt import AuthJWTBearer
from main.appodus_utils.response.success_response import SuccessResponse
from main.appodus_utils.router import AppRouter

release_router = AppRouter(prefix="/admin/verifications", tags=["Admin — Release"])

_auth = AuthJWTBearer(required_permissions=["MANAGE_VERIFICATIONS"])


@release_router.post("/{vid}/release", response_model=SuccessResponse[ReleaseDto])
async def release_report(
    vid: str,
    svc: ReleaseService = Depends(lambda: __import__("kink", fromlist=["di"]).di[ReleaseService]),
    claims=Depends(_auth),
):
    result = await svc.release(vid, admin_id=claims.sub)
    return SuccessResponse.ok(result)


@release_router.post("/{vid}/fail-release", response_model=SuccessResponse[ReleaseDto])
async def fail_release(
    vid: str,
    body: FailReleaseDto,
    svc: ReleaseService = Depends(lambda: __import__("kink", fromlist=["di"]).di[ReleaseService]),
    claims=Depends(_auth),
):
    result = await svc.fail_release(vid, admin_id=claims.sub, reason=body.reason)
    return SuccessResponse.ok(result)
