"""Bot session admin controller (PRD §7.6, §7.11, D57).

URL shape: /admin/whatsapp/bot — RBAC-gated (CONFIGURE_SYSTEM). Frontend service:
frontend/src/components/admin/chat/libs/whatsapp-bot-service.

Two things an agent working the console needs, and one an operator does:

* **See whether the bot is answering a thread.** D57 makes `HUMAN` sticky, so a thread can
  be silent for reasons that are entirely invisible from the message list.
* **Hand it back.** The only way out of `HUMAN`. Without this control the first agent
  reply would silence a conversation permanently, which is a worse failure than the one
  stickiness prevents.
* **Ask whether the channel is ready** (§7.11) — which transport and classifier are live,
  and whether the classifier is actually configured. The answer never includes a key.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from kink import di

from main.app.domain.channel.whatsapp.bot.session.models import (
    BotChannelReadinessDto,
    BotSessionDto,
)
from main.app.domain.channel.whatsapp.bot.session.service import WhatsAppBotSessionService
from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.appodus_utils.db.models import SuccessResponse

whatsapp_bot_router = APIRouter(prefix="/admin/whatsapp/bot", tags=["Admin: WhatsApp Bot"])
whatsapp_bot_session_service: WhatsAppBotSessionService = di[WhatsAppBotSessionService]


@whatsapp_bot_router.get("/readiness", response_model=SuccessResponse[BotChannelReadinessDto])
async def channel_readiness(
    _admin_id: str = Depends(require_permission(Permission.CONFIGURE_SYSTEM)),
):
    """Whether the channel is wired for live traffic (§7.11 launch gate).

    Reports configuration, never credentials: "a key is set" is the operational fact, and
    the key itself is not something an endpoint should be able to say.
    """
    return SuccessResponse[BotChannelReadinessDto](
        data=await whatsapp_bot_session_service.readiness()
    )


@whatsapp_bot_router.get("/sessions/{phone_e164}", response_model=SuccessResponse[BotSessionDto])
async def get_session(
    phone_e164: str,
    _admin_id: str = Depends(require_permission(Permission.CONFIGURE_SYSTEM)),
):
    """This number's bot state — mode, current flow, and why it last escalated."""
    return SuccessResponse[BotSessionDto](
        data=await whatsapp_bot_session_service.describe(phone_e164)
    )


@whatsapp_bot_router.post(
    "/sessions/{phone_e164}/hand-back", response_model=SuccessResponse[BotSessionDto]
)
async def hand_back(
    phone_e164: str,
    _admin_id: str = Depends(require_permission(Permission.CONFIGURE_SYSTEM)),
):
    """Give the thread back to the bot — the explicit half of D57's sticky mode."""
    await whatsapp_bot_session_service.hand_back(phone_e164)
    # Described rather than mapped from the returned row: the console needs the §7.7
    # window state alongside the mode, and `describe` is the one place that resolves it.
    return SuccessResponse[BotSessionDto](
        data=await whatsapp_bot_session_service.describe(phone_e164)
    )
