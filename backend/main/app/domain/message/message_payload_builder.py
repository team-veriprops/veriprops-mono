from typing import List, Dict, Any

from kink import inject

from main.app.config.settings import settings
from main.app.domain.user.service import UserService
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.integrations.messaging.models import MessageRequestRecipient, EmailRecipient, \
    MessageRecipientUserId, \
    MessageContextModule, UserContactDto, MessageContext


@inject
@decorate_all_methods(transactional(), exclude=['__init__'], exclude_startswith=['_'])
@decorate_all_methods(method_trace_logger, exclude=['__init__'])
class MessageRecipientBuilder:
    def __init__(self,
                 user_service: UserService
                 ):
        self._user_service = user_service

    async def build_global_context(self, context=None) -> dict[MessageContext, Any]:
        if context is None:
            context = {}
        context: Dict[MessageContext, Any] = context

        context.update({
            MessageContext.TODAY: Utils.datetime_now(),
            MessageContext.BRAND: settings.BRAND,
            MessageContext.BRAND_SUPPORT_EMAIL: settings.BRAND_SUPPORT_EMAIL,
            MessageContext.BRAND_SUPPORT_PHONE: settings.BRAND_SUPPORT_PHONE,
        })

        return context

    async def build_recipient_and_context(
            self,
            recipient: MessageRecipientUserId,
            context_modules: List[MessageContextModule]
    ) -> tuple[MessageRequestRecipient, Dict[str, Any]]:
        """Single DB fetch: returns both the recipient and the template context."""
        user_contact: UserContactDto = await self._user_service.get_user_contact(user_id=recipient.user_id)
        cc = await self._user_service.get_email_recipients(recipient.cc_recipients)
        bcc = await self._user_service.get_email_recipients(recipient.bcc_recipients)

        built_recipient = self._contact_to_recipient(user_contact, recipient.user_id, cc, bcc)
        context = self._build_context_from_contact(user_contact, context_modules)
        return built_recipient, context

    def _contact_to_recipient(
            self,
            user_contact: UserContactDto,
            user_id: str,
            cc: list,
            bcc: list
    ) -> MessageRequestRecipient:
        return MessageRequestRecipient(
            user_id=user_id,
            fullname=user_contact.full_name,
            email=EmailRecipient(email=user_contact.email, fullname=user_contact.full_name),
            phone=user_contact.phone if user_contact.phone else None,
            ios_push_token=user_contact.ios_push_token,
            android_push_token=user_contact.android_push_token,
            web_push_token=user_contact.web_push_token,
            cc_recipient=cc,
            bcc_recipient=bcc,
        )

    def _build_context_from_contact(
            self,
            user_contact: UserContactDto,
            context_modules: List[MessageContextModule]
    ) -> Dict[str, Any]:
        context: Dict[MessageContext, Any] = {}
        for module in context_modules:
            if module == MessageContextModule.USER:
                context.update({
                    MessageContext.PHONE: user_contact.phone,
                    MessageContext.EMAIL: user_contact.email,
                    MessageContext.FIRST_NAME: user_contact.first_name,
                    MessageContext.LAST_NAME: user_contact.last_name,
                    MessageContext.FULL_NAME: user_contact.full_name,
                })
        return context
# class MessageContext(str, Enum):
#     BRAND = "BRAND"
#     OTP = "OTP"
#     LINK = "LINK"
#     TODAY = "TODAY"
#     EMAIL = "EMAIL"
#     FIRST_NAME = "FIRST_NAME"
#     LAST_NAME = "LAST_NAME"
#     FULL_NAME = "FULL_NAME"
#     VALIDITY = "VALIDITY"
#     BRAND_SUPPORT_EMAIL = "BRAND_SUPPORT_EMAIL"
#     BRAND_SUPPORT_PHONE = "BRAND_SUPPORT_PHONE"