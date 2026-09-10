"""Inbound WhatsApp message journal (PRD §26.3.3, §26.8).

Every message Meta delivers is recorded here before anything acts on it, which buys three
things at once:

* **Exactly-once handling.** Meta retries a delivery until it gets a 2xx, so the same
  `wamid` can arrive several times. The unique index is what makes a redelivery a no-op
  instead of a duplicate conversation turn — and it is what lets the webhook acknowledge
  everything it has authenticated.
* **The §26.8 record.** Chat logs are retained business records covered by the same access
  controls as case data; the raw payload is kept so the legal pack reflects what actually
  arrived, not our interpretation of it.
* **Channel analytics (§26.10).** Voice-note volume — the trigger for v1.1
  transcription-assist — is a count over this table.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Column, Index, String, Text, UniqueConstraint

from main.appodus_utils import BaseEntity, BaseQueryDto, InternalPageRequest, Object
from main.appodus_utils.db.models import JSONB_VARIANT, UTCDateTime
from main.appodus_utils.integrations.messaging.providers.whatsapp.inbound import InboundKind


# ─── ORM ──────────────────────────────────────────────────────────

class WhatsAppInboundMessage(BaseEntity):
    __tablename__ = "whatsapp_inbound_messages"

    # Meta's message id — the dedup key, and the reason redelivery is safe.
    wamid = Column(String(128), nullable=False)
    from_phone = Column(String(20), nullable=False)
    kind = Column(String(20), nullable=False)
    # Body, caption, or interactive reply title, with the §26.4.1 `[ref: …]` marker
    # already lifted out (D85). Null for a location pin or contact card.
    text = Column(Text, nullable=True)
    # The widget page code the customer arrived through (§26.4.1, §26.10). Null when they
    # messaged the number directly, which is real demand too — the analytics repo counts
    # those under `direct` rather than dropping them.
    page_code = Column(String(40), nullable=True)
    # Menu selection id — never the display copy, so flows don't depend on wording.
    interactive_id = Column(String(64), nullable=True)
    media_id = Column(String(128), nullable=True)
    media_mime_type = Column(String(100), nullable=True)
    sender_name = Column(String(120), nullable=True)
    # Exactly what Meta sent, retained for the §26.8 record.
    payload = Column(JSONB_VARIANT, nullable=True)
    received_at = Column(UTCDateTime, nullable=True)
    # Set once the message has been routed; a null value marks an ingest that failed
    # partway, so it can be found rather than silently lost.
    processed_at = Column(UTCDateTime, nullable=True)
    # The console message this produced, when it produced one.
    chat_message_id = Column(String(36), nullable=True)

    __table_args__ = (
        UniqueConstraint("wamid", name="uq_whatsapp_inbound_wamid"),
        Index("ix_whatsapp_inbound_from_phone", "from_phone"),
        Index("ix_whatsapp_inbound_messages_chat_message_id", "chat_message_id"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateWhatsAppInboundMessageDto(Object):
    wamid: str
    from_phone: str
    kind: InboundKind
    text: Optional[str] = None
    page_code: Optional[str] = None
    interactive_id: Optional[str] = None
    media_id: Optional[str] = None
    media_mime_type: Optional[str] = None
    sender_name: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    received_at: Optional[datetime] = None
    chat_message_id: Optional[str] = None


class UpdateWhatsAppInboundMessageDto(Object):
    chat_message_id: Optional[str] = None


class QueryWhatsAppInboundMessageDto(BaseQueryDto):
    wamid: Optional[str] = None
    from_phone: Optional[str] = None
    kind: Optional[str] = None


class SearchWhatsAppInboundMessageDto(InternalPageRequest, BaseQueryDto):
    from_phone: Optional[str] = None
    kind: Optional[str] = None
