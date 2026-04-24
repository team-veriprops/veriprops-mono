import re
from typing import Dict, List, Optional, Set, ClassVar, TypeVar, Type

from cachetools.func import lru_cache
from pydantic import EmailStr, Field, PrivateAttr, field_validator, ConfigDict

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
    headers: List[Dict[str, str]] = Field(default_factory=list)
    priority: MessagePriority = MessagePriority.NORMAL
    sandbox_mode: bool = False
    categories: Optional[List[str]] = Field(default_factory=list)
    subjects: Dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of subject keys to email subject templates"
    )

    # Private attributes
    _normalized_subjects: Dict[str, str] = PrivateAttr()

    # Class-level constants
    _required_subjects: ClassVar[Set[str]] = {
        # '2fa',
        # 'account_activation',
        # 'account_deactivation',
        # 'agent_performance_summary',
        # 'buyer_canceled_visit',
        # 'buyer_referral_incentive',
        # 'buyer_scheduled_visit',
        # 'buyer_tips_content',
        # 'buyer_tour_reminder',
        # 'counter_offer_received',
        'email_verification',
        # 'escrow_initiated',
        # 'escrow_status_update',
        # 'feedback_request_post_transaction',
        # 'fraud_warning_alert',
        # 'holiday_festive_greeting',
        # 'id_document_rejected_accepted',
        # 'id_document_verification_pending',
        # 'inactive_user_reengagement',
        # 'inquiry_confirmation',
        # 'invite_test_new_feature',
        # 'limited_time_promo_discount',
        # 'listing_pending_moderation',
        # 'listing_performance_summary',
        # 'login_diff_device_security_alert',
        # 'name_update_success',
        # 'new_agent_welcome',
        # 'new_buyer_lead_alert',
        # 'new_buyer_welcome',
        # 'new_feature_announcement',
        # 'new_message_from_seller_agent',
        # 'new_property_match_saved_search',
        # 'new_review_for_agent',
        'new_user_email_verification',
        'new_user_welcome',
        # 'offer_accepted',
        # 'offer_received_to_seller',
        # 'offer_rejected',
        # 'offer_submitted_confirmation',
        'password_reset_request',
        'password_update_success',
        'phone_verification',
        # 'post_sale_buyer_feedback_request',
        # 'post_sale_seller_feedback_request',
        # 'price_drop_saved_property',
        # 'price_suggestion_trends',
        # 'property_listed_success',
        # 'property_listing_completion_reminder',
        # 'property_rejected_with_reasons',
        # 'referral_program_invitation',
        # 'schedule_tour_confirmation',
        # 'seller_replied_to_inquiry',
        # 'seller_referral_incentive',
        # 'seller_tips_content',
        # 'survey_product_improvement',
        # 'terms_policy_updates',
        # 'tour_rescheduled_cancelled',
        # 'transaction_completed',
        # 'transaction_failed_declined',
    }

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

    @field_validator('subjects')
    @classmethod
    def validate_subjects(cls, v: Dict[str, str]) -> Dict[str, str]:
        normalized_keys = {k.replace('_subject', '').lower() for k in v}
        missing = cls._required_subjects - normalized_keys
        if missing:
            raise ValueError(f"Missing required subjects: {', '.join(sorted(missing))}")

        for key, value in v.items():
            if len(value) > 150:
                raise ValueError(f"Subject '{key}' exceeds 150 character limit")
        return v

    # --- Init hook ---
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._normalized_subjects = {
            k.replace('_subject', '').lower(): v
            for k, v in self.subjects.items()
        }

    # --- Cached subject lookup ---
    @lru_cache(maxsize=54)
    def get_subject(self, key: str) -> str:
        """O(1) subject lookup."""
        normalized = key.replace('_subject', '').lower()
        if subject := self._normalized_subjects.get(normalized):
            return subject
        raise KeyError(f"Invalid subject key: {key}")

    # --- Constructor from app settings ---
    @classmethod
    def from_settings(cls: Type[T]) -> T:
        """Preferred constructor from settings."""
        return cls(
            from_email=settings.EMAIL_FROM_ADDRESS,
            from_name=settings.EMAIL_FROM_NAME,
            sms_ttl=settings.SMS_TTL,
            sms_sender_id=settings.SMS_SENDER_ID,
            headers=settings.MESSAGING_HEADERS or [],
            priority=settings.MESSAGING_PRIORITY,
            sandbox_mode=settings.MESSAGING_SANDBOX_MODE,
            categories=settings.MESSAGING_CATEGORIES,
            subjects=settings.EMAIL_SUBJECTS
        )
