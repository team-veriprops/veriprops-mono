"""SSE streaming endpoint for customer verification updates (S33).

GET /api/portal/verifications/{vid}/stream

Authenticates customer, validates ownership, subscribes to Redis channel
`verifications:{vid}`, and streams events. 60-second heartbeat keeps the
connection alive through proxies. Falls back gracefully when Redis is unavailable.
"""
from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator

from fastapi import Depends, HTTPException
from sse_starlette.sse import EventSourceResponse

from main.app.domain.verification.portal.tracking import TrackingService
from main.app.domain.verification.repo import VerificationRepo
from main.appodus_utils.auth.jwt import AuthJWTBearer
from main.appodus_utils.router import AppRouter

stream_router = AppRouter(prefix="/portal/verifications", tags=["Portal — SSE"])

_auth = AuthJWTBearer()
_HEARTBEAT_INTERVAL = 60  # seconds


async def _event_generator(vid: str, customer_id: str, verification_id: str) -> AsyncGenerator:
    """Subscribe to Redis and yield SSE events with a 60-second heartbeat."""
    try:
        from kink import di
        from redis.asyncio import Redis
        redis_client: Redis = di[Redis]
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(f"verifications:{verification_id}")

        try:
            while True:
                # Wait up to heartbeat_interval for a message
                message_task = asyncio.create_task(pubsub.get_message(ignore_subscribe_messages=True, timeout=None))
                try:
                    msg = await asyncio.wait_for(asyncio.shield(message_task), timeout=_HEARTBEAT_INTERVAL)
                    if msg and msg.get("type") == "message":
                        try:
                            data = json.loads(msg["data"])
                        except (json.JSONDecodeError, TypeError):
                            data = {"raw": str(msg["data"])}
                        yield {"event": data.get("event", "update"), "data": json.dumps(data)}
                except asyncio.TimeoutError:
                    # Send heartbeat (comment line per SSE spec)
                    yield {"event": "heartbeat", "data": "ping"}
                finally:
                    message_task.cancel()
        finally:
            await pubsub.unsubscribe(f"verifications:{verification_id}")
            await pubsub.aclose()

    except Exception:
        # Redis unavailable — stream a single status update and close
        yield {"event": "unavailable", "data": json.dumps({"message": "Live updates unavailable"})}


def stream_router_get_tracking():
    return stream_router


@stream_router.get("/{vid}/stream")
async def stream_verification(
    vid: str,
    ver_repo: VerificationRepo = Depends(lambda: __import__("kink", fromlist=["di"]).di[VerificationRepo]),
    claims=Depends(_auth),
):
    ver = await ver_repo.get_by_vid(vid)
    if ver is None:
        raise HTTPException(status_code=404, detail="Verification not found")
    if ver.customer_id != claims.sub:
        raise HTTPException(status_code=403, detail="Access denied")

    return EventSourceResponse(
        _event_generator(vid, customer_id=claims.sub, verification_id=str(ver.id))
    )
