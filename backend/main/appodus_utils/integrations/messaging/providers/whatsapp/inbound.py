"""Inbound WhatsApp normalization (PRD §7.3.3).

Meta posts every kind of event to one webhook: customer messages, delivery receipts, and
account notices, all wrapped in a deeply nested envelope whose shape varies per message
type. This module is the single place that understands that envelope. Everything
downstream — the bot engine, the console adapter, the fraud scan — consumes
``InboundWhatsAppMessage`` and never sees Meta's JSON, so a Cloud API version bump is a
change here and nowhere else.

Robustness is a security property, not a nicety: the webhook is a public endpoint, so a
malformed or unfamiliar payload must normalize to "nothing to do" rather than raise.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from main.appodus_utils import Object
from main.appodus_utils.integrations.messaging.providers.whatsapp.phone import to_e164


class InboundKind(str, enum.Enum):
    """What a customer sent, normalized across Meta's per-type payload shapes."""

    TEXT = "TEXT"
    INTERACTIVE = "INTERACTIVE"   # button or list reply — a menu selection
    IMAGE = "IMAGE"
    DOCUMENT = "DOCUMENT"
    VIDEO = "VIDEO"
    AUDIO = "AUDIO"               # includes voice notes (§7.6.3, §7.10)
    STICKER = "STICKER"
    LOCATION = "LOCATION"
    CONTACTS = "CONTACTS"
    UNSUPPORTED = "UNSUPPORTED"   # a type Meta added after this code was written


# Meta's `type` discriminator → our kind. Anything absent here is UNSUPPORTED and gets
# routed to a human rather than dropped.
_KIND_BY_META_TYPE: Dict[str, InboundKind] = {
    "text": InboundKind.TEXT,
    "interactive": InboundKind.INTERACTIVE,
    "image": InboundKind.IMAGE,
    "document": InboundKind.DOCUMENT,
    "video": InboundKind.VIDEO,
    "audio": InboundKind.AUDIO,
    "sticker": InboundKind.STICKER,
    "location": InboundKind.LOCATION,
    "contacts": InboundKind.CONTACTS,
}

_MEDIA_KINDS = {
    InboundKind.IMAGE,
    InboundKind.DOCUMENT,
    InboundKind.VIDEO,
    InboundKind.AUDIO,
    InboundKind.STICKER,
}


class InboundWhatsAppMessage(Object):
    """One customer message, in the form the rest of the system understands."""

    wamid: str                                   # Meta's message id — the dedup key
    from_phone: str                              # E.164, the cross-channel identity key
    kind: InboundKind
    text: Optional[str] = None                   # body, caption, or reply title
    interactive_id: Optional[str] = None         # menu selection id, never display copy
    media_id: Optional[str] = None               # Meta media handle (fetched on demand)
    media_mime_type: Optional[str] = None
    sender_name: Optional[str] = None            # WhatsApp profile name, when supplied
    received_at: Optional[datetime] = None
    raw: Dict[str, Any] = {}                     # the original message object, retained
                                                 # for the §7.8 record and later replay


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _timestamp(raw: Any) -> Optional[datetime]:
    try:
        return datetime.fromtimestamp(int(raw), tz=timezone.utc)
    except (TypeError, ValueError):
        return None


def _clean(text: Any) -> Optional[str]:
    if not isinstance(text, str):
        return None
    stripped = text.strip()
    return stripped or None


def _interactive_reply(message: Dict[str, Any]) -> Dict[str, Any]:
    """A button reply and a list reply carry the same `{id, title}` under different keys."""
    interactive = _as_dict(message.get("interactive"))
    for key in ("button_reply", "list_reply"):
        reply = _as_dict(interactive.get(key))
        if reply:
            return reply
    return {}


def _normalize_message(
    message: Dict[str, Any], names_by_wa_id: Dict[str, str]
) -> Optional[InboundWhatsAppMessage]:
    wamid = message.get("id")
    if not isinstance(wamid, str) or not wamid:
        # The wamid is how a redelivery is recognised; without one we cannot promise
        # exactly-once handling, so the safe move is to ignore the message.
        return None

    wa_id = str(message.get("from") or "")
    kind = _KIND_BY_META_TYPE.get(str(message.get("type") or ""), InboundKind.UNSUPPORTED)

    text: Optional[str] = None
    interactive_id: Optional[str] = None
    media_id: Optional[str] = None
    media_mime_type: Optional[str] = None

    if kind == InboundKind.TEXT:
        text = _clean(_as_dict(message.get("text")).get("body"))
    elif kind == InboundKind.INTERACTIVE:
        reply = _interactive_reply(message)
        interactive_id = _clean(reply.get("id"))
        text = _clean(reply.get("title"))
    elif kind in _MEDIA_KINDS:
        media = _as_dict(message.get(str(message.get("type"))))
        media_id = _clean(media.get("id"))
        media_mime_type = _clean(media.get("mime_type"))
        text = _clean(media.get("caption"))

    return InboundWhatsAppMessage(
        wamid=wamid,
        from_phone=to_e164(wa_id),
        kind=kind,
        text=text,
        interactive_id=interactive_id,
        media_id=media_id,
        media_mime_type=media_mime_type,
        sender_name=names_by_wa_id.get(wa_id),
        received_at=_timestamp(message.get("timestamp")),
        raw=message,
    )


def normalize_webhook(payload: Dict[str, Any]) -> List[InboundWhatsAppMessage]:
    """Every customer message in a Meta webhook body, in delivery order.

    Delivery receipts, account notices, and malformed bodies yield an empty list — the
    caller acknowledges them and does nothing.
    """
    messages: List[InboundWhatsAppMessage] = []

    for entry in _as_list(_as_dict(payload).get("entry")):
        for change in _as_list(_as_dict(entry).get("changes")):
            value = _as_dict(_as_dict(change).get("value"))

            # Meta supplies the sender's profile name alongside, not inside, the message.
            names_by_wa_id: Dict[str, str] = {}
            for contact in _as_list(value.get("contacts")):
                contact = _as_dict(contact)
                name = _clean(_as_dict(contact.get("profile")).get("name"))
                wa_id = contact.get("wa_id")
                if name and isinstance(wa_id, str):
                    names_by_wa_id[wa_id] = name

            for raw_message in _as_list(value.get("messages")):
                normalized = _normalize_message(_as_dict(raw_message), names_by_wa_id)
                if normalized is not None:
                    messages.append(normalized)

    return messages
