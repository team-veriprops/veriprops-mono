"""WebSocket endpoint for real-time thread messaging (S37).

WS /api/ws/threads/{thread_id}

Auth: reads the JWT from the `Authorization` query parameter (WebSocket doesn't
      support HTTP-only cookies the same way; the frontend must pass the token
      as `?token=<jwt>` or via the cookie header on the initial handshake).
      Falls back gracefully when Redis is unavailable — client can poll REST.
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

ws_router = APIRouter(prefix="/ws", tags=["WebSocket — Threads"])

_HEARTBEAT_INTERVAL = 30  # seconds


async def _thread_event_loop(websocket: WebSocket, thread_id: str) -> None:
    try:
        from kink import di
        from redis.asyncio import Redis
        redis_client: Redis = di[Redis]
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(f"thread:{thread_id}")
        try:
            while True:
                msg_task = asyncio.create_task(
                    pubsub.get_message(ignore_subscribe_messages=True, timeout=None)
                )
                try:
                    msg = await asyncio.wait_for(asyncio.shield(msg_task), timeout=_HEARTBEAT_INTERVAL)
                    if msg and msg.get("type") == "message":
                        try:
                            data = json.loads(msg["data"])
                        except (json.JSONDecodeError, TypeError):
                            data = {"raw": str(msg["data"])}
                        await websocket.send_json(data)
                except asyncio.TimeoutError:
                    await websocket.send_json({"event": "heartbeat"})
                finally:
                    msg_task.cancel()
        finally:
            await pubsub.unsubscribe(f"thread:{thread_id}")
            await pubsub.aclose()
    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await websocket.send_json({"event": "unavailable", "message": "Live updates unavailable"})
        except Exception:
            pass


@ws_router.websocket("/threads/{thread_id}")
async def thread_websocket(
    websocket: WebSocket,
    thread_id: str,
):
    # Minimal auth: validate JWT from query param or cookie
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001)
        return

    try:
        from libre_fastapi_jwt import AuthJWT
        # We create a mock request-like object; libre_fastapi_jwt supports cookie or header
        # For WebSocket, fall back to manual decode
        import jwt as pyjwt
        from main.app.config.settings import settings
        pyjwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except Exception:
        await websocket.close(code=4003)
        return

    await websocket.accept()
    await _thread_event_loop(websocket, thread_id)
