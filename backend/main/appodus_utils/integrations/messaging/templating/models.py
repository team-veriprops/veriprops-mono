from enum import Enum


class AvailableTemplate(str, Enum):
    """
    Enum representing all available notification templates in the system,
    categorized by their purpose and including supported delivery channels.
    """

    # ============ ACCOUNT & SECURITY ============
    NEW_USER_WELCOME = "new_user_welcome"  # Email, WhatsApp, Mobile push
    NEW_ADMIN_USER_INVITE = "new_admin_user_invite" # Email
    NEW_NORMAL_USER_INVITE = "new_normal_user_invite" # Email
    NEW_BUYER_WELCOME = "new_buyer_welcome"  # Email, WhatsApp, Mobile push
    NEW_AGENT_WELCOME = "new_agent_welcome"  # Email, WhatsApp, Mobile push
    NEW_USER_EMAIL_VERIFICATION = "new_user_email_verification"  # Email
    EMAIL_VERIFICATION = "email_verification"  # Email
    PHONE_VERIFICATION = "phone_verification"  # SMS, WhatsApp
    NAME_UPDATE_SUCCESS= "name_update_success" # Email
    LOGIN_DIFF_DEVICE_SECURITY_ALERT = "login_diff_device_security_alert"  # SMS, Email, WhatsApp, Mobile push
    PASSWORD_UPDATE_SUCCESS = "password_update_success"  # Email
    PASSWORD_RESET_REQUEST = "password_reset_request"  # SMS, Email
    PASSWORD_RESET_SUCCESS = "password_reset_success"  # Email
    TWO_FA = "2fa"  # SMS, Email, WhatsApp
    ACCOUNT_DEACTIVATION = "account_deactivation"  # Email
    ACCOUNT_ACTIVATION = "account_activation"  # Email
    PROPERTY_LISTING_COMPLETION_REMINDER = "property_listing_completion_reminder"  # Email, WhatsApp, Mobile push

    # ============ LISTING MANAGEMENT ============
    PROPERTY_LISTED_SUCCESS = "property_listed_success"  # Email, WhatsApp
    PROPERTY_REJECTED_REASONS = "property_rejected_with_reasons"  # Email
    LISTING_PENDING_MODERATION = "listing_pending_moderation"  # Email
    LISTING_PERFORMANCE_SUMMARY = "listing_performance_summary"  # Email, WhatsApp
    PRICE_SUGGESTION_TRENDS = "price_suggestion_trends"  # Email, WhatsApp

    # ============ BUYER NOTIFICATIONS ============
    NEW_PROPERTY_MATCH_SAVED_SEARCH = "new_property_match_saved_search"  # Email, Mobile push, Web Push
    PRICE_DROP_SAVED_PROPERTY = "price_drop_saved_property"  # Email, Mobile push, Web Push
    SELLER_REPLIED_TO_INQUIRY = "seller_replied_to_inquiry"  # Email, WhatsApp, Mobile push, Web Push
    NEW_MESSAGE_FROM_SELLER_AGENT = "new_message_from_seller_agent"  # Email, WhatsApp, Mobile push
    INQUIRY_CONFIRMATION = "inquiry_confirmation"  # Email
    SCHEDULE_TOUR_CONFIRMATION = "schedule_tour_confirmation"  # SMS, Email, WhatsApp, Mobile push, Web Push
    TOUR_RESCHEDULED_CANCELLED = "tour_rescheduled_cancelled"  # SMS, Email, WhatsApp, Mobile push, Web Push

    # ============ REMINDERS & ALERTS ============
    BUYER_TOUR_REMINDER = "buyer_tour_reminder"  # SMS, Email, WhatsApp, Mobile push, Web Push
    INACTIVE_USER_REENGAGEMENT = "inactive_user_reengagement"  # Email, WhatsApp, Mobile push, Web Push

    # ============ AGENT ENGAGEMENT ============
    NEW_BUYER_LEAD_ALERT = "new_buyer_lead_alert"  # Email, WhatsApp, Mobile push
    BUYER_SCHEDULED_VISIT = "buyer_scheduled_visit"  # Email, WhatsApp, Mobile push
    BUYER_CANCELED_VISIT = "buyer_canceled_visit"  # Email, WhatsApp, Mobile push
    AGENT_PERFORMANCE_SUMMARY = "agent_performance_summary"  # Email
    NEW_REVIEW_FOR_AGENT = "new_review_for_agent"  # Email, Mobile push

    # ============ TRANSACTIONS ============
    OFFER_SUBMITTED_CONFIRMATION = "offer_submitted_confirmation"  # Email
    OFFER_RECEIVED_TO_SELLER = "offer_received_to_seller"  # Email, WhatsApp, Mobile push
    OFFER_ACCEPTED = "offer_accepted"  # Email, WhatsApp, Mobile push
    OFFER_REJECTED = "offer_rejected"  # Email
    COUNTER_OFFER_RECEIVED = "counter_offer_received"  # Email, WhatsApp, Mobile push
    ESCROW_INITIATED = "escrow_initiated"  # Email, WhatsApp
    ESCROW_STATUS_UPDATE = "escrow_status_update"  # Email, WhatsApp
    TRANSACTION_COMPLETED = "transaction_completed"  # Email, WhatsApp, Mobile push
    TRANSACTION_FAILED_DECLINED = "transaction_failed_declined"  # SMS, Email, WhatsApp

    # ============ POST-SALE & FOLLOW-UP ============
    POST_SALE_BUYER_FEEDBACK_REQUEST = "post_sale_buyer_feedback_request"  # Email, WhatsApp, Mobile push
    POST_SALE_SELLER_FEEDBACK_REQUEST = "post_sale_seller_feedback_request"  # Email, WhatsApp, Mobile push
    BUYER_REFERRAL_INCENTIVE = "buyer_referral_incentive"  # Email, WhatsApp, Mobile push
    SELLER_REFERRAL_INCENTIVE = "seller_referral_incentive"  # Email, WhatsApp, Mobile push

    # ============ TRUST & SAFETY ============
    ID_DOCUMENT_VERIFICATION_PENDING = "id_document_verification_pending"  # Email, Mobile push
    ID_DOCUMENT_REJECTED_ACCEPTED = "id_document_rejected_accepted"  # Email
    FRAUD_WARNING_ALERT = "fraud_warning_alert"  # SMS, Email, WhatsApp, Mobile push
    TERMS_POLICY_UPDATES = "terms_policy_updates"  # Email

    # ============ PRODUCT UPDATES ============
    NEW_FEATURE_ANNOUNCEMENT = "new_feature_announcement"  # Email, Mobile push, Web Push
    INVITE_TEST_NEW_FEATURE = "invite_test_new_feature"  # Email
    FEEDBACK_REQUEST_POST_TRANSACTION = "feedback_request_post_transaction"  # Email, WhatsApp, Mobile push
    SURVEY_PRODUCT_IMPROVEMENT = "survey_product_improvement"  # Email, WhatsApp

    # ============ MARKETING ============
    SELLER_TIPS_CONTENT = "seller_tips_content"  # Email, Mobile push, Web Push
    BUYER_TIPS_CONTENT = "buyer_tips_content"  # Email, Mobile push, Web Push
    REFERRAL_PROGRAM_INVITATION = "referral_program_invitation"  # Email, WhatsApp, Mobile push
    HOLIDAY_FESTIVE_GREETING = "holiday_festive_greeting"  # Email, WhatsApp
    LIMITED_TIME_PROMO_DISCOUNT = "limited_time_promo_discount"  # Email, WhatsApp, Mobile push, Web Push
