"""The §7.10 fact writer (WA-43, D80).

One method, called from the handful of seams where a countable thing happens. Two
properties make it safe to sprinkle through the conversation path:

* **It never raises.** Analytics is a courtesy on top of something that already happened —
  a customer was answered, a link was minted, a payment succeeded. A metric write that
  could fail the turn would trade the channel's reliability for a number on a dashboard,
  which is the wrong way round. The same reasoning as `bot/sender.py` and
  `milestones.py`: best-effort, logged, never fatal.
* **It writes facts, not state.** Nothing reads these rows back to make a decision, so a
  lost row costs one count, never a wrong answer to a customer.

Call sites are deliberately few and each one is the *single* place its fact can occur —
`ESCALATED` is written in `WhatsAppBotSessionService.note_escalation`, for instance, because
every one of the nine `EscalationReason`s already funnels through it. A fact recorded at
each of nine call sites would be nine chances to add a tenth reason and forget.
"""
from __future__ import annotations

from logging import Logger
from typing import Optional

from kink import di, inject

from main.app.domain.channel.whatsapp.analytics.models import (
    CreateWhatsAppChannelEventDto,
    WhatsAppChannelEventType,
)
from main.app.domain.channel.whatsapp.analytics.repo import WhatsAppChannelEventRepo
from main.app.domain.channel.whatsapp.bot.session.models import EscalationReason
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger

logger: Logger = di["logger"]


@inject
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class ChannelEventRecorder:
    """Writes one §7.10 fact, and swallows anything that goes wrong doing it.

    Deliberately **not** `@transactional`: it is called from inside a transaction that
    belongs to the thing being counted, and opening its own would either nest pointlessly
    or let a metric write commit independently of the turn it describes.
    """

    def __init__(self, whatsapp_channel_event_repo: WhatsAppChannelEventRepo):
        self._events = whatsapp_channel_event_repo

    async def record(
        self,
        event_type: WhatsAppChannelEventType,
        *,
        phone_e164: Optional[str] = None,
        page_code: Optional[str] = None,
        reason: Optional[EscalationReason] = None,
        verification_id: Optional[str] = None,
        customer_id: Optional[str] = None,
        detail: Optional[dict] = None,
    ) -> None:
        """Append one fact. Failure is logged and dropped, never raised."""
        try:
            await self._events.create(
                CreateWhatsAppChannelEventDto(
                    occurred_at=Utils.datetime_now(),
                    event_type=event_type.value,
                    phone_e164=phone_e164,
                    page_code=page_code,
                    reason=reason.value if reason else None,
                    verification_id=verification_id,
                    customer_id=customer_id,
                    detail=detail,
                )
            )
        except Exception:  # pragma: no cover - defensive, exercised by its own unit test
            logger.exception(
                "Failed to record WhatsApp channel event %s (§7.10) — dropping it rather "
                "than failing the turn that caused it.",
                event_type.value,
            )

    async def record_payment_if_channel_case(
        self, verification_id: str, customer_id: Optional[str]
    ) -> None:
        """§7.10's seam-conversion numerator, recorded only for cases this channel produced.

        The check is what keeps the metric honest: `PAYMENT_CONFIRMED` fires for every
        payment on the platform, and counting all of them against a WhatsApp intake
        denominator would report a conversion rate well over 100%. A case belongs to the
        channel when the channel already wrote a fact about it — which `INTAKE_REDEEMED`
        and `PAY_LINK_ISSUED` both do.
        """
        try:
            if not await self._events.has_events_for_verification(verification_id):
                return
        except Exception:  # pragma: no cover - defensive
            logger.exception(
                "Failed to check WhatsApp channel origin for verification %s (§7.10).",
                verification_id,
            )
            return
        await self.record(
            WhatsAppChannelEventType.PAYMENT_COMPLETED,
            verification_id=verification_id,
            customer_id=customer_id,
        )
