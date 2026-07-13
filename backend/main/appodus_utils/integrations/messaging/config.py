import re
from typing import Dict, List, Optional, TypeVar, Type

from pydantic import EmailStr, Field, field_validator, ConfigDict

from main.app.config.settings import settings
from main.appodus_utils import Object
from main.appodus_utils.exception.exceptions import ValidationException
from main.appodus_utils.integrations.messaging.models import MessagePriority

T = TypeVar("T", bound="MessagingConfig")

class MessagingConfig(Object):
    """Immutable messaging configuration with validated fields."""

    # Public fields (immutable by convention)
    from_email: EmailStr
    from_name: str = Field(..., min_length=1, max_length=100)
    sms_ttl: int = Field(..., gt=60, le=86400)
    sms_sender_id: str = Field(..., min_length=1, max_length=11)
    headers: Dict[str, str] = Field(default_factory=dict)
    priority: MessagePriority = MessagePriority.NORMAL
    sandbox_mode: bool = False
    categories: Optional[List[str]] = Field(default_factory=list)

    # Pydantic v2 config
    model_config = ConfigDict(
        frozen=True,  # Makes instances immutable
        extra='forbid',  # Prevents extra fields
        str_strip_whitespace=True,  # Auto-trim strings
    )

    @field_validator('from_name')
    @classmethod
    def validate_from_name(cls, v: str) -> str:
        if not re.match(r'^[\w\s\-\.]+$', v):
            raise ValueError("From name contains invalid characters")
        return v

    @field_validator('sms_sender_id')
    @classmethod
    def validate_sms_id(cls, v: str) -> str:
        if not re.match(r'^[a-zA-Z0-9\s]+$', v):
            raise ValidationException("SMS SENDER ID allows only alphanumeric chars and spaces")
        return v

    # --- Constructor from app settings ---
    @classmethod
    def from_settings(cls: Type[T]) -> T:
        """Preferred constructor from settings."""
        return cls(
            from_email=settings.EMAIL_FROM_ADDRESS,
            from_name=settings.EMAIL_FROM_NAME,
            sms_ttl=settings.SMS_TTL,
            sms_sender_id=settings.SMS_SENDER_ID,
            headers=settings.MESSAGING_HEADERS or {},
            priority=settings.MESSAGING_PRIORITY,
            sandbox_mode=settings.MESSAGING_SANDBOX_MODE,
            categories=settings.MESSAGING_CATEGORIES,
        )
