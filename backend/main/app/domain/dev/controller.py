"""Dev/QA endpoints (non-production only). URL shape: /dev/...

Production-gated twice (CLAUDE.md automation determinism): this router is only mounted in
non-prod (see app/domain/__init__.py), and every handler calls `_require_non_prod()` which
returns 404 in production.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from kink import di

from main.app.config.settings import settings
from main.app.domain.dev.scenario import BuildScenarioDto, DevScenarioService, ScenarioDto
from main.app.domain.dev.service import DevSeedService
from main.appodus_utils.config.settings import Environment
from main.appodus_utils import Object
from main.appodus_utils.db.models import SuccessResponse
from main.appodus_utils.exception.exceptions import ResourceNotFoundException
from main.app.domain.channel.whatsapp.handoff.models import HandoffIntent
from main.appodus_utils.integrations.messaging.providers.whatsapp.inbound import (
    InboundKind,
    WhatsAppDeliveryStatus,
)

dev_router = APIRouter(prefix="/dev", tags=["Dev"])
service: DevSeedService = di[DevSeedService]
scenario_service: DevScenarioService = di[DevScenarioService]


def _require_non_prod() -> None:
    """404 in production — the second guard behind the non-prod router mount."""
    if settings.ENVIRONMENT == Environment.PRODUCTION:
        raise ResourceNotFoundException(resource="Not found")


@dev_router.post("/reset", response_model=SuccessResponse[dict])
async def reset():
    _require_non_prod()
    return SuccessResponse[dict](data=await service.reset())


@dev_router.post("/seed", response_model=SuccessResponse[dict])
async def seed():
    _require_non_prod()
    return SuccessResponse[dict](data=await service.seed())


@dev_router.post("/scenario", response_model=SuccessResponse[ScenarioDto])
async def build_scenario(req: BuildScenarioDto):
    """Build an isolated verification standing at a lifecycle stage — its own customer and
    its own approved agents, every transition driven through the real services — so a
    browser spec can start mid-journey without depending on another spec's actions."""
    _require_non_prod()
    return SuccessResponse[ScenarioDto](data=await scenario_service.build(req))


@dev_router.get("/messages/latest", response_model=SuccessResponse[dict])
async def latest_message(recipient: str):
    """Bookkeeping snapshot of the newest outbound message to *recipient* — lets the
    drive-through's messaging_retry stage assert stored/retrying/failed/sent state."""
    _require_non_prod()
    return SuccessResponse[dict](data=await service.latest_message(recipient))


@dev_router.post("/messages/rewind", response_model=SuccessResponse[dict])
async def rewind_message(recipient: str, rewind_expiry: bool = False):
    """Pull the newest matching message's next_retry_at (and optionally expires_at) into
    the past so the retry sweep fires immediately — determinism helper for e2e runs
    against the default backoff ladder."""
    _require_non_prod()
    return SuccessResponse[dict](data=await service.rewind_message(recipient, rewind_expiry))


# ── WhatsApp channel (PRD §26, D43) ────────────────────────────────
# The stub transport has no external counterpart to drive it, so these two endpoints are
# how an automated run plays both sides of a conversation: inject what a customer
# "sent", then read back what Veriprops would have replied. Same double prod gate as the
# rest of this router.


class InjectWhatsAppInboundDto(Object):
    """Body for a simulated Meta delivery. A DTO rather than embedded `Body` scalars so
    the wire stays camelCase like every other endpoint — `Body(embed=True)` binds the raw
    Python parameter name and would quietly break that convention."""

    from_phone: str
    text: Optional[str] = None
    kind: InboundKind = InboundKind.TEXT
    wamid: Optional[str] = None
    sender_name: Optional[str] = None
    interactive_id: Optional[str] = None


class InjectWhatsAppStatusDto(Object):
    """Body for a simulated Meta receipt about a message we sent (D92). ``wamid`` is the id
    the stub transport recorded in the outbox for that send."""

    wamid: str
    status: WhatsAppDeliveryStatus
    error_codes: list[int] = []


class IssueHandoffTokenDto(Object):
    case_id: str
    customer_id: str
    intent: HandoffIntent = HandoffIntent.PAY


@dev_router.post("/whatsapp/inbound", response_model=SuccessResponse[dict])
async def inject_whatsapp_inbound(req: InjectWhatsAppInboundDto):
    """Deliver an inbound WhatsApp message as if Meta had posted it.

    Enters the same ingestion path as a real signed delivery — thread resolution, fraud
    scan, console post — so an e2e run exercises the production code, not a shortcut.
    """
    _require_non_prod()
    return SuccessResponse[dict](data=await service.inject_whatsapp_inbound(
        from_phone=req.from_phone,
        text=req.text,
        kind=req.kind.value,
        wamid=req.wamid,
        sender_name=req.sender_name,
        interactive_id=req.interactive_id,
    ))


@dev_router.post("/whatsapp/status", response_model=SuccessResponse[dict])
async def inject_whatsapp_status(req: InjectWhatsAppStatusDto):
    """Deliver a delivery/read receipt as if Meta had posted it — through the same
    `WhatsAppStatusService` a signed webhook reaches, so ticks, read state and the
    bookkeeping row are exercised for real."""
    _require_non_prod()
    return SuccessResponse[dict](data=await service.inject_whatsapp_status(
        wamid=req.wamid, status=req.status.value, error_codes=req.error_codes,
    ))


@dev_router.post("/assistant/sweep", response_model=SuccessResponse[dict])
async def sweep_assistant_turns(waiting_seconds: float = 0):
    """Answer pending web assistant turns now (D93) — the sweep a long-running host would run
    every minute. *waiting_seconds* defaults to no grace, so a test can leave a turn orphaned
    and prove it is recovered without sleeping."""
    _require_non_prod()
    from kink import di as _di

    from main.app.domain.communication.assistant.web import WebAssistantService

    return SuccessResponse[dict](
        data=await _di[WebAssistantService].sweep(waiting_seconds=waiting_seconds)
    )


@dev_router.post("/whatsapp/handoff-token", response_model=SuccessResponse[dict])
async def issue_handoff_token(req: IssueHandoffTokenDto):
    """Mint a handoff link for a case — the entry point the /wa landings need before the
    bot flows that normally issue them exist."""
    _require_non_prod()
    return SuccessResponse[dict](data=await service.issue_handoff_token(
        case_id=req.case_id, customer_id=req.customer_id, intent=req.intent.value,
    ))


@dev_router.get("/whatsapp/outbox", response_model=SuccessResponse[dict])
async def whatsapp_outbox(recipient: Optional[str] = None):
    """What the stub transport recorded — the assertion surface for outbound copy."""
    _require_non_prod()
    return SuccessResponse[dict](data=await service.whatsapp_outbox(recipient))


@dev_router.delete("/whatsapp/outbox", response_model=SuccessResponse[dict])
async def clear_whatsapp_outbox():
    """Reset the recorded outbound messages so a scenario starts from a known point."""
    _require_non_prod()
    return SuccessResponse[dict](data=await service.clear_whatsapp_outbox())


@dev_router.post("/whatsapp/rewind-window", response_model=SuccessResponse[dict])
async def rewind_whatsapp_window(phone: str, hours: int = 25):
    """Age a number's inbound journal so Meta's 24-hour window reads as closed (§26.7).

    Without it the drive-through cannot reach the `window_reopen` path or the reply queue
    behind it — the window is derived from when the customer last wrote, and a test does
    not get to wait a day.
    """
    _require_non_prod()
    return SuccessResponse[dict](data=await service.rewind_whatsapp_window(phone, hours))


@dev_router.post("/whatsapp/fail-next-turn", response_model=SuccessResponse[dict])
async def arm_whatsapp_bot_failure():
    """Make the next bot turn fail, once — the §26.11 failure drill (§26.6.5, WA-40).

    The launch gate asks for the fallback to be *tested*, not just implemented: kill the
    bot, observe the auto-reply and the console alert. Unit tests prove the `except` branch
    behaves; only a live turn proves a real failure reaches it rather than becoming a 500 in
    the webhook and a Meta retry.
    """
    _require_non_prod()
    return SuccessResponse[dict](data=await service.arm_whatsapp_bot_failure())
