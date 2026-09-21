"""Assistant admin controller (PRD §26.6, §26.11, §16.7, D57, D93).

URL shape: /admin/assistant. Session read + hand-back are `MANAGE_VERIFICATIONS` — the
permission that lets an admin reply, so every admin who can take a thread over can also see
and undo it, and the banner never 403s an ops admin into `/forbidden` on a per-case thread.
Readiness stays `CONFIGURE_SYSTEM` — launch-readiness configuration, not a reply-time need.
Frontend service: frontend/src/components/chat/libs/assistant-service.

Three things an admin working the console needs:

* **See whether the assistant is answering a thread.** D57 makes `HUMAN` sticky, so a thread
  can be silent for reasons that are entirely invisible from the message list.
* **Hand it back.** The only way out of `HUMAN`. Without this control the first reply would
  silence a conversation permanently, which is a worse failure than the one stickiness
  prevents.
* **Ask whether the channel is ready** (§26.11) — which transport and classifier are live,
  and whether the classifier is actually configured. The answer never includes a key.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from kink import di

from main.app.domain.communication.assistant.session.models import (
    AssistantReadinessDto,
    AssistantSessionDto,
)
from main.app.domain.communication.assistant.session.service import AssistantSessionService
from main.app.domain.communication.assistant.surface import assistant_surface_for
from main.app.domain.communication.conversation.service import ConversationService
from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.appodus_utils.db.models import SuccessResponse

assistant_router = APIRouter(prefix="/admin/assistant", tags=["Admin: Assistant"])
assistant_session_service: AssistantSessionService = di[AssistantSessionService]
conversation_service: ConversationService = di[ConversationService]


@assistant_router.get("/readiness", response_model=SuccessResponse[AssistantReadinessDto])
async def readiness(
    _admin_id: str = Depends(require_permission(Permission.CONFIGURE_SYSTEM)),
):
    """Whether the assistant is wired for live traffic (§26.11 launch gate).

    `CONFIGURE_SYSTEM`, unlike the session read/hand-back below: this is operational
    configuration for launch-readiness, not something every admin who can reply needs.
    Reports configuration, never credentials — "a key is set" is the operational fact, and
    the key itself is not something an endpoint should be able to say.
    """
    return SuccessResponse[AssistantReadinessDto](data=await assistant_session_service.readiness())


@assistant_router.get(
    "/sessions/{conversation_id}", response_model=SuccessResponse[AssistantSessionDto]
)
async def get_session(
    conversation_id: str,
    _admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    """This thread's assistant state — mode, current flow, and why it last escalated."""
    conversation = await conversation_service.get_for_admin(conversation_id)
    return SuccessResponse[AssistantSessionDto](
        data=await assistant_session_service.describe(
            conversation, enabled=assistant_surface_for(conversation) is not None
        )
    )


@assistant_router.post(
    "/sessions/{conversation_id}/hand-back", response_model=SuccessResponse[AssistantSessionDto]
)
async def hand_back(
    conversation_id: str,
    _admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    """Give the thread back to the assistant — the explicit half of D57's sticky mode."""
    conversation = await conversation_service.get_for_admin(conversation_id)
    await assistant_session_service.hand_back(conversation_id)
    # Described rather than mapped from the returned row: the console needs the §26.7 window
    # state alongside the mode, and `describe` is the one place that resolves it.
    return SuccessResponse[AssistantSessionDto](
        data=await assistant_session_service.describe(
            conversation, enabled=assistant_surface_for(conversation) is not None
        )
    )
