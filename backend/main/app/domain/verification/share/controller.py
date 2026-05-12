"""Share link endpoints — S43."""
from __future__ import annotations

from fastapi import Depends

from main.app.domain.verification.share.models import CreateShareDto, ShareLinkDto
from main.app.domain.verification.share.service import ShareService
from main.appodus_utils.auth.jwt import AuthJWTBearer, JWTClaims
from main.appodus_utils.response.success_response import SuccessResponse
from main.appodus_utils.router import AppRouter
from kink import di

share_router = AppRouter(prefix="/portal/verifications", tags=["Portal — Share"])

_auth = AuthJWTBearer()


@share_router.post("/{vid}/share", response_model=SuccessResponse[ShareLinkDto])
async def create_share(vid: str, dto: CreateShareDto, claims: JWTClaims = Depends(_auth)):
    svc: ShareService = di[ShareService]
    link = await svc.create(vid, claims.sub, dto)
    return SuccessResponse.ok(link)


@share_router.delete("/{vid}/share/{link_id}", response_model=SuccessResponse[None])
async def revoke_share(vid: str, link_id: str, claims: JWTClaims = Depends(_auth)):
    svc: ShareService = di[ShareService]
    await svc.revoke(link_id, claims.sub)
    return SuccessResponse.ok(None)


@share_router.post("/public/share/{token}/acknowledge", response_model=SuccessResponse[None])
async def acknowledge_share(token: str):
    svc: ShareService = di[ShareService]
    await svc.acknowledge(token)
    return SuccessResponse.ok(None)
