"""Customer tracking & evidence controller (PRD §9, §4.9).

URL shape: /verifications/{id}/... — customer-owned (JWT subject must own the
verification). Frontend service: frontend/src/components/portal/libs/verification-service.

Real-time: ``GET /stream`` is the single SSE endpoint; ``GET /tracking`` is the 60-second
polling fallback and returns the *same* snapshot body (§4.9). Ownership is verified inside
the request handler (session-backed) before the stream begins; the streaming generator
itself touches no DB — it only forwards in-memory emitter events and heartbeats, so it is
safe after the per-request session closes.
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from kink import di
from libre_fastapi_jwt import AuthJWT

from main.app.core.realtime import VerificationEventType
from main.app.core.realtime.emitter import VerificationEventEmitter
from main.app.domain.audit.models import AuditActivityPageDto
from main.app.domain.verification.service import VerificationService
from main.app.domain.verification.tracking.models import (
    CustomerEvidenceDto,
    VerificationListItemDto,
    VerificationTrackingDto,
)
from main.app.domain.verification.tracking.service import CustomerTrackingService
from main.appodus_utils.db.models import Page, SuccessResponse

customer_tracking_router = APIRouter(prefix="/verifications", tags=["Verification Tracking"])
tracking_service: CustomerTrackingService = di[CustomerTrackingService]
verification_service: VerificationService = di[VerificationService]

# Emit a heartbeat if no real event arrives within this window — keeps proxies/mobile
# connections alive and confirms liveness to the client.
_HEARTBEAT_SECONDS = 25


def _sse_frame(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@customer_tracking_router.get("", response_model=SuccessResponse[Page[VerificationListItemDto]])
async def list_my_verifications(
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=10, ge=1, le=50),
    authorize: AuthJWT = Depends(),
):
    await authorize.jwt_required()
    customer_id = str(authorize.get_jwt_subject())
    result = await tracking_service.list_my_verifications(customer_id, page, page_size)
    return SuccessResponse[Page[VerificationListItemDto]](data=result)


@customer_tracking_router.get(
    "/{verification_id}/tracking", response_model=SuccessResponse[VerificationTrackingDto]
)
async def get_tracking(verification_id: str, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    customer_id = str(authorize.get_jwt_subject())
    snapshot = await tracking_service.get_snapshot(verification_id, customer_id)
    return SuccessResponse[VerificationTrackingDto](data=snapshot)


@customer_tracking_router.get(
    "/{verification_id}/evidence", response_model=SuccessResponse[Page[CustomerEvidenceDto]]
)
async def get_evidence(
    verification_id: str,
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=10, ge=1, le=50),
    authorize: AuthJWT = Depends(),
):
    await authorize.jwt_required()
    customer_id = str(authorize.get_jwt_subject())
    result = await tracking_service.list_evidence(verification_id, customer_id, page, page_size)
    return SuccessResponse[Page[CustomerEvidenceDto]](data=result)


@customer_tracking_router.get(
    "/{verification_id}/activity", response_model=SuccessResponse[AuditActivityPageDto]
)
async def get_activity(
    verification_id: str,
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=20, ge=1, le=100),
    authorize: AuthJWT = Depends(),
):
    await authorize.jwt_required()
    customer_id = str(authorize.get_jwt_subject())
    result = await tracking_service.activity(verification_id, customer_id, page, page_size)
    return SuccessResponse[AuditActivityPageDto](data=result)


@customer_tracking_router.get("/{verification_id}/stream")
async def stream(verification_id: str, request: Request, authorize: AuthJWT = Depends()):
    """SSE stream of live verification events (§4.9). Cookie-authenticated (EventSource
    cannot set headers). Ownership is checked here, before streaming begins."""
    await authorize.jwt_required()
    customer_id = str(authorize.get_jwt_subject())
    # Session-backed ownership gate up front — raises 404/403 before we open the stream.
    await verification_service.get_owned(verification_id, customer_id)

    emitter: VerificationEventEmitter = di[VerificationEventEmitter]

    async def _events():
        async with emitter.subscribe(verification_id) as queue:
            # Nudge the client to pull the authoritative snapshot on connect.
            yield _sse_frame(VerificationEventType.TASK_UPDATED.value, {})
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_SECONDS)
                    yield _sse_frame(payload["event"], payload["data"])
                except asyncio.TimeoutError:
                    yield _sse_frame(VerificationEventType.HEARTBEAT.value, {})

    return StreamingResponse(
        _events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable proxy buffering so events flush immediately
        },
    )
