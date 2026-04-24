import re
from html import escape
from typing import Dict, Any, Optional

import bleach
from pydantic import field_validator

from main.appodus_utils import Object
from main.appodus_utils.integrations.exception.exceptions import IntegrationTemplateException
from main.appodus_utils.integrations.messaging.models import MessageChannel


class MessageValidator:
    PHONE_REGEX = r"^\+[1-9]\d{1,14}$"  # E.164 format
    EMAIL_REGEX = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    WHATSAPP_ID_REGEX = r"^[0-9]{1,15}$"

    @classmethod
    def validate_recipient(cls, channel: MessageChannel, recipient: str) -> bool:
        """Validate recipient based on channel"""
        if channel == MessageChannel.SMS:
            return bool(re.match(cls.PHONE_REGEX, recipient))
        elif channel == MessageChannel.EMAIL:
            return bool(re.match(cls.EMAIL_REGEX, recipient))
        elif channel == MessageChannel.WHATSAPP:
            return bool(re.match(cls.WHATSAPP_ID_REGEX, recipient))
        elif channel == MessageChannel.PUSH:
            return len(recipient) > 0  # Just non-empty for push tokens
        return False

    @classmethod
    def sanitize_content(cls, channel: MessageChannel, content: Dict) -> Dict:
        """Sanitize message content based on channel"""
        sanitized = content.copy()

        if channel == MessageChannel.SMS:
            if "text" in sanitized:
                sanitized["text"] = cls._sanitize_text(sanitized["text"])

        elif channel == MessageChannel.EMAIL:
            if "subject" in sanitized:
                sanitized["subject"] = cls._sanitize_text(sanitized["subject"])
            if "body" in sanitized:
                sanitized["body"] = cls._sanitize_html(sanitized["body"])

        elif channel == MessageChannel.WHATSAPP:
            if "text" in sanitized:
                sanitized["text"] = cls._sanitize_text(sanitized["text"])
            if "caption" in sanitized:
                sanitized["caption"] = cls._sanitize_text(sanitized["caption"])

        return sanitized

    @staticmethod
    def _sanitize_text(text: str) -> str:
        """Basic text sanitization"""
        text = escape(text)
        text = text.replace("\r\n", "\n")  # Normalize line endings
        return text[:2000]  # Truncate to reasonable length

    @staticmethod
    def _sanitize_html(html: str) -> str:
        """HTML sanitization with allowed tags"""
        allowed_tags = [
            "a", "p", "br", "strong", "em", "ul", "ol", "li", "h1", "h2", "h3"
        ]
        allowed_attrs = {
            "a": ["href", "title", "target"]
        }
        return bleach.clean(
            html,
            tags=allowed_tags,
            attributes=allowed_attrs,
            strip=True
        )


class ValidatedMessage(Object):
    channel: MessageChannel
    recipient: str
    content: Dict[str, Any]
    extras: Optional[Dict] = None

    @field_validator('recipient')
    def validate_recipient_format(cls, v, values):
        if 'channel' not in values:
            raise ValueError("Channel must be set before recipient validation")
        if not MessageValidator.validate_recipient(values['channel'], v):
            raise IntegrationTemplateException(
                f"Invalid recipient format for channel {values['channel']}"
            )
        return v

    @field_validator('content')
    def validate_and_sanitize_content(cls, v, values):
        if 'channel' not in values:
            raise ValueError("Channel must be set before content validation")

        channel = values['channel']
        try:
            return MessageValidator.sanitize_content(channel, v)
        except Exception as e:
            raise IntegrationTemplateException(f"Content validation failed: {str(e)}")
