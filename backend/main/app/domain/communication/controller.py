"""Communication controllers (PRD §11, §N, §4.9).

Three mounted routers:
- ``chat_router`` (/chat/...) — the shared, member-gated surface: conversation list, unread
  counter, per-user SSE stream, per-conversation message feed + read + send.
- ``verification_chat_router`` — thread openers for the two verification channels
  (customer-owned and agent-assigned) plus general support.
- ``admin_chat_router`` (/admin/messages, /admin/verifications/{id}/chat) — RBAC-gated hold
  review queue + admin thread open/send.

Delivery is over ``GET /chat/stream`` (SSE); sends are ordinary HTTP POST (§4.9).
Frontend service: frontend/src/components/chat/libs/chat-service.
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from kink import di
from libre_fastapi_jwt import AuthJWT

from main.app.core.realtime.user_emitter import UserEventEmitter, UserEventType
from main.app.domain.communication.chat_message.models import (
    ChatMessage,
    ChatMessageDto,
    HeldMessageDto,
    MessageKind,
    SenderKind,
)
from main.app.domain.communication.conversation.models import ConversationDto, ConversationType
from main.app.domain.communication.service import CommunicationService
from main.app.domain.communication.chat_message.service import HELD_NOTICE
from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.appodus_utils import Object
from main.appodus_utils.db.models import Page, SuccessResponse

chat_router = APIRouter(prefix="/chat", tags=["Chat"])
verification_chat_router = APIRouter(tags=["Chat"])
admin_chat_router = APIRouter(prefix="/admin", tags=["Admin: Chat"])

comms: CommunicationService = di[CommunicationService]

_HEARTBEAT_SECONDS = 25


# ─── Request bodies (defined before the routes reference them) ────────

class SendMessageBodyDto(Object):
    body: str
    kind: MessageKind = MessageKind.CHAT


class AgentSendMessageDto(Object):
    body: str
    task_id: str | None = None


class AdminSendMessageDto(Object):
    body: str
    task_id: str | None = None
    conversation_type: ConversationType = ConversationType.ADMIN_AGENT


class SendToConversationDto(Object):
    body: str
    # sender_kind is intentionally NOT accepted from the client — it is derived
    # server-side from the caller's role and the thread type (see post_message).
    task_id: str | None = None
    kind: MessageKind = MessageKind.CHAT


def _sse_frame(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _convo_dto(convo) -> ConversationDto:
    return ConversationDto(
        id=convo.id,
        type=ConversationType(convo.type),
        verification_id=convo.verification_id,
        subject=convo.subject,
        last_message_at=convo.last_message_at,
        closed=convo.closed,
    )


def _sent_dto(message: ChatMessage) -> ChatMessageDto:
    """Projection of the just-sent message back to its sender (carries the held notice)."""
    from main.app.core.state.status import ChatMessageState

    held = message.state == ChatMessageState.HELD.value
    return ChatMessageDto(
        id=message.id,
        conversation_id=message.conversation_id,
        body=message.body,
        task_id=message.task_id,
        state=ChatMessageState(message.state),
        message_kind=MessageKind(message.message_kind),
        clarification_status=None,
        sender=_sender_self(message),
        held_notice=HELD_NOTICE if held else None,
        date_created=message.date_created,
        delivered_at=message.delivered_at,
    )


def _sender_self(message: ChatMessage):
    from main.app.domain.communication.chat_message.models import ChatSenderDto

    return ChatSenderDto(user_id=message.sender_user_id, kind=SenderKind(message.sender_kind))


# ─────────────────────────────────────────────────────────────────────
# Shared member-gated surface (/chat)
# ─────────────────────────────────────────────────────────────────────

@chat_router.get("/conversations", response_model=SuccessResponse[list[ConversationDto]])
async def list_conversations(authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    return SuccessResponse[list[ConversationDto]](data=await comms.list_conversations(user_id))


@chat_router.get("/unread", response_model=SuccessResponse[dict])
async def unread_count(authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    return SuccessResponse[dict](data={"count": await comms.unread_count(user_id)})


@chat_router.get(
    "/conversations/{conversation_id}/messages",
    response_model=SuccessResponse[Page[ChatMessageDto]],
)
async def list_messages(
    conversation_id: str,
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=30, ge=1, le=100),
    authorize: AuthJWT = Depends(),
):
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    result = await comms.list_messages(conversation_id, user_id, page, page_size)
    return SuccessResponse[Page[ChatMessageDto]](data=result)


@chat_router.post("/conversations/{conversation_id}/read", response_model=SuccessResponse[dict])
async def mark_read(conversation_id: str, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    await comms.mark_read(conversation_id, user_id)
    return SuccessResponse[dict](data={"count": await comms.unread_count(user_id)})


@chat_router.post(
    "/conversations/{conversation_id}/messages", response_model=SuccessResponse[ChatMessageDto]
)
async def post_message(
    conversation_id: str,
    req: "SendToConversationDto",
    authorize: AuthJWT = Depends(),
):
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    message = await comms.post_message(
        conversation_id, user_id, req.body, task_id=req.task_id, kind=req.kind
    )
    return SuccessResponse[ChatMessageDto](data=_sent_dto(message))


@chat_router.get("/stream")
async def stream(request: Request, authorize: AuthJWT = Depends()):
    """Per-user SSE stream for chat + notification pushes (§4.9, §N). Cookie-authenticated."""
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    emitter: UserEventEmitter = di[UserEventEmitter]

    async def _events():
        async with emitter.subscribe(user_id) as queue:
            yield _sse_frame(UserEventType.HEARTBEAT.value, {})
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_SECONDS)
                    yield _sse_frame(payload["event"], payload["data"])
                except asyncio.TimeoutError:
                    yield _sse_frame(UserEventType.HEARTBEAT.value, {})

    return StreamingResponse(
        _events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ─────────────────────────────────────────────────────────────────────
# Thread openers (customer / agent / support)
# ─────────────────────────────────────────────────────────────────────

@verification_chat_router.get(
    "/verifications/{verification_id}/chat", response_model=SuccessResponse[ConversationDto]
)
async def open_customer_thread(verification_id: str, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    customer_id = str(authorize.get_jwt_subject())
    convo = await comms.customer_thread(verification_id, customer_id)
    return SuccessResponse[ConversationDto](data=_convo_dto(convo))


@verification_chat_router.post(
    "/verifications/{verification_id}/chat/messages", response_model=SuccessResponse[ChatMessageDto]
)
async def customer_send(
    verification_id: str, req: "SendMessageBodyDto", authorize: AuthJWT = Depends()
):
    await authorize.jwt_required()
    customer_id = str(authorize.get_jwt_subject())
    message = await comms.customer_send(verification_id, customer_id, req.body, kind=req.kind)
    return SuccessResponse[ChatMessageDto](data=_sent_dto(message))


@verification_chat_router.get("/support/chat", response_model=SuccessResponse[ConversationDto])
async def open_support_thread(authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    convo = await comms.support_thread(user_id)
    return SuccessResponse[ConversationDto](data=_convo_dto(convo))


@verification_chat_router.post("/support/chat/messages", response_model=SuccessResponse[ChatMessageDto])
async def support_send(req: "SendMessageBodyDto", authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    user_id = str(authorize.get_jwt_subject())
    message = await comms.support_send(user_id, req.body)
    return SuccessResponse[ChatMessageDto](data=_sent_dto(message))


@verification_chat_router.get(
    "/agents/verifications/{verification_id}/chat", response_model=SuccessResponse[ConversationDto]
)
async def open_agent_thread(verification_id: str, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    agent_id = str(authorize.get_jwt_subject())
    convo = await comms.agent_thread(verification_id, agent_id)
    return SuccessResponse[ConversationDto](data=_convo_dto(convo))


@verification_chat_router.post(
    "/agents/verifications/{verification_id}/chat/messages",
    response_model=SuccessResponse[ChatMessageDto],
)
async def agent_send(
    verification_id: str, req: "AgentSendMessageDto", authorize: AuthJWT = Depends()
):
    await authorize.jwt_required()
    agent_id = str(authorize.get_jwt_subject())
    message = await comms.agent_send(verification_id, agent_id, req.body, task_id=req.task_id)
    return SuccessResponse[ChatMessageDto](data=_sent_dto(message))


# ─────────────────────────────────────────────────────────────────────
# Admin surface (RBAC-gated)
# ─────────────────────────────────────────────────────────────────────

@admin_chat_router.get("/messages/held", response_model=SuccessResponse[Page[HeldMessageDto]])
async def held_queue(
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=20, ge=1, le=100),
    _admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    return SuccessResponse[Page[HeldMessageDto]](data=await comms.held_queue(page, page_size))


@admin_chat_router.post("/messages/{message_id}/approve", response_model=SuccessResponse[dict])
async def approve_message(
    message_id: str, admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS))
):
    message = await comms.approve_message(message_id, admin_id)
    return SuccessResponse[dict](data={"id": message.id, "state": message.state})


@admin_chat_router.post("/messages/{message_id}/reject", response_model=SuccessResponse[dict])
async def reject_message(
    message_id: str, admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS))
):
    message = await comms.reject_message(message_id, admin_id)
    return SuccessResponse[dict](data={"id": message.id, "state": message.state})


@admin_chat_router.get(
    "/verifications/{verification_id}/chat", response_model=SuccessResponse[ConversationDto]
)
async def open_admin_thread(
    verification_id: str,
    conversation_type: ConversationType = Query(default=ConversationType.CUSTOMER_ADMIN, alias="type"),
    admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    convo = await comms.admin_thread(verification_id, conversation_type, admin_id)
    return SuccessResponse[ConversationDto](data=_convo_dto(convo))


@admin_chat_router.post(
    "/verifications/{verification_id}/chat/messages", response_model=SuccessResponse[ChatMessageDto]
)
async def admin_send(
    verification_id: str,
    req: "AdminSendMessageDto",
    admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    message = await comms.admin_send(
        verification_id, req.conversation_type, admin_id, req.body, task_id=req.task_id
    )
    return SuccessResponse[ChatMessageDto](data=_sent_dto(message))
