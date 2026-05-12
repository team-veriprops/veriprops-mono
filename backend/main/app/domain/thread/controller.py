"""Thread REST endpoints (S37).

GET  /api/threads/{thread_id}/messages  — paginated message list
POST /api/threads/{thread_id}/messages  — post a new message
GET  /api/threads/by-verification/{vid} — get/create customer↔admin thread
GET  /api/threads/by-task/{task_id}     — get/create admin↔agent thread
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from kink import di

from main.app.domain.thread.models import (
    PostMessageDto,
    SenderRole,
    ThreadDto,
    ThreadMessageDto,
    ThreadType,
)
from main.app.domain.thread.service import ThreadService
from main.app.domain.user.auth.utils.permissions import require_admin
from main.appodus_utils.auth.jwt import AuthJWTBearer
from main.appodus_utils.db.models import SuccessResponse

thread_router = APIRouter(prefix="/threads", tags=["Threads"])
thread_service: ThreadService = di[ThreadService]
_auth = AuthJWTBearer()


@thread_router.get(
    "/by-verification/{vid}",
    response_model=SuccessResponse[ThreadDto],
)
async def get_customer_admin_thread(
    vid: str,
    claims=Depends(_auth),
):
    thread = await thread_service.get_or_create_thread(
        verification_id=vid,
        thread_type=ThreadType.CUSTOMER_ADMIN,
    )
    return SuccessResponse.ok(thread)


@thread_router.get(
    "/by-task/{task_id}",
    response_model=SuccessResponse[ThreadDto],
)
async def get_admin_agent_thread(
    task_id: str,
    verification_id: str,
    claims=Depends(_auth),
):
    thread = await thread_service.get_or_create_thread(
        verification_id=verification_id,
        thread_type=ThreadType.ADMIN_AGENT,
        task_id=task_id,
    )
    return SuccessResponse.ok(thread)


@thread_router.get(
    "/{thread_id}/messages",
    response_model=SuccessResponse[List[ThreadMessageDto]],
)
async def list_messages(
    thread_id: str,
    limit: int = 50,
    claims=Depends(_auth),
):
    messages = await thread_service.list_messages(thread_id, limit=limit)
    return SuccessResponse.ok(messages)


@thread_router.post(
    "/{thread_id}/messages",
    response_model=SuccessResponse[ThreadMessageDto],
)
async def post_message(
    thread_id: str,
    body: PostMessageDto,
    claims=Depends(_auth),
):
    from main.app.domain.user.auth.session.models import UserType
    sender_role = (
        SenderRole.ADMIN
        if (claims.user_type or "").upper() == UserType.ADMIN.value
        else SenderRole.CUSTOMER
    )
    # Agent role override: agents post in ADMIN_AGENT threads
    if (claims.user_type or "").upper() == "AGENT":
        sender_role = SenderRole.AGENT

    msg = await thread_service.post_message(
        thread_id=thread_id,
        sender_id=claims.sub,
        sender_role=sender_role,
        dto=body,
    )
    return SuccessResponse.ok(msg)
