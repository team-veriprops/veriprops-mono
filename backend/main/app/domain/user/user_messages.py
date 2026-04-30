from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger
from typing import Any, List

from kink import di, inject

from main.app.domain.message.message_sender import BaseMessageSender
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.integrations.messaging.templating.models import AvailableTemplate
from main.appodus_utils.integrations.messaging.models import MessageRecipientUserId, MessageContextModule, \
    MessageCategory, \
    MessageChannel, MessageRequestRecipient, MessageContext

logger: Logger = di["logger"]


@inject
@decorate_all_methods(method_trace_logger, exclude=[''])
class AccountSecurityMessages(BaseMessageSender):
    """Handles all account security and verification related messages"""

    async def send_direct_new_user_welcome_message(self, recipient: MessageRequestRecipient,  context: dict[MessageContext, Any]):
        await self._send_direct_message(
            recipient=recipient,
            template=AvailableTemplate.NEW_USER_WELCOME,
            context=context,
            category=MessageCategory.ONBOARDING,
            default_channels=[
                MessageChannel.WHATSAPP,
                MessageChannel.EMAIL,
                MessageChannel.SMS
            ]
        )


    async def send_direct_admin_user_invite_message(self, recipient: MessageRequestRecipient,  context: dict[MessageContext, Any]):
        await self._send_direct_message(
            recipient=recipient,
            template=AvailableTemplate.NEW_ADMIN_USER_INVITE,
            context=context,
            category=MessageCategory.ONBOARDING,
            default_channels=[
                MessageChannel.EMAIL
            ]
        )


    # async def send_direct_normal_user_invite_message(self, recipient: MessageRequestRecipient,  context: dict[str, Any]):
    #     await self._send_direct_message(
    #         recipient=recipient,
    #         template=AvailableTemplate.NEW_NORMAL_USER_INVITE,
    #         context=context,
    #         category=MessageCategory.ONBOARDING,
    #         default_channels=[
    #             MessageChannel.EMAIL
    #         ]
    #     )

    # async def send_email_verification_message(self, recipient_user_id: MessageRecipientUserId,
    #                                           context_modules:List[MessageContextModule], extra_context: dict[str, Any]):
    #     await self._send_message(
    #         recipient_user_id=recipient_user_id,
    #         template=AvailableTemplate.EMAIL_VERIFICATION,
    #         context_modules=context_modules,
    #         category=MessageCategory.VERIFICATION,
    #         default_channels=[
    #             MessageChannel.EMAIL
    #         ],
    #         extra_context=extra_context
    #     )

    async def send_direct_email_verification_message(self, recipient: MessageRequestRecipient,  context: dict[MessageContext, Any]):
        await self._send_direct_message(
            recipient=recipient,
            template=AvailableTemplate.EMAIL_VERIFICATION,
            context=context,
            category=MessageCategory.VERIFICATION,
            default_channels=[
                MessageChannel.EMAIL
            ]
        )

    # async def send_phone_verification_message(self, recipient_user_id: MessageRecipientUserId,
    #                                           context_modules:List[MessageContextModule], extra_context: dict[str, Any]):
    #     await self._send_message(
    #         recipient_user_id=recipient_user_id,
    #         template=AvailableTemplate.PHONE_VERIFICATION,
    #         context_modules=context_modules,
    #         category=MessageCategory.VERIFICATION,
    #         default_channels=[
    #             MessageChannel.SMS,
    #             MessageChannel.WHATSAPP
    #         ],
    #         extra_context=extra_context
    #     )

    async def send_direct_phone_verification_message(self, recipient: MessageRequestRecipient,  context: dict[MessageContext, Any]):
        await self._send_direct_message(
            recipient=recipient,
            template=AvailableTemplate.PHONE_VERIFICATION,
            context=context,
            category=MessageCategory.VERIFICATION,
            default_channels=[
                MessageChannel.SMS
            ]
        )

    async def send_login_security_alert_message(self, recipient_user_id: MessageRecipientUserId,
                                                context_modules:List[MessageContextModule]):
        await self._send_message(
            recipient_user_id=recipient_user_id,
            template=AvailableTemplate.LOGIN_DIFF_DEVICE_SECURITY_ALERT,
            context_modules=context_modules,
            category=MessageCategory.SECURITY,
            default_channels=[
                MessageChannel.SMS,
                MessageChannel.WHATSAPP,
                MessageChannel.EMAIL,
                MessageChannel.PUSH
            ]
        )

    async def send_password_reset_request_message(self, recipient_user_id: MessageRecipientUserId,
                                                  context_modules:List[MessageContextModule], extra_context: dict[MessageContext, Any]):
        await self._send_message(
            recipient_user_id=recipient_user_id,
            template=AvailableTemplate.PASSWORD_RESET_REQUEST,
            context_modules=context_modules,
            category=MessageCategory.SECURITY,
            default_channels=[
                MessageChannel.EMAIL
            ],
            extra_context=extra_context
        )

    # async def send_password_updated_message(self, recipient_user_id: MessageRecipientUserId,
    #                                         context_modules:List[MessageContextModule]):
    #     await self._send_message(
    #         recipient_user_id=recipient_user_id,
    #         template=AvailableTemplate.PASSWORD_UPDATE_SUCCESS,
    #         context_modules=context_modules,
    #         category=MessageCategory.SECURITY,
    #         default_channels=[MessageChannel.EMAIL]
    #     )

    # async def send_name_updated_message(self, recipient_user_id: MessageRecipientUserId,
    #                                         context_modules:List[MessageContextModule]):
    #     await self._send_message(
    #         recipient_user_id=recipient_user_id,
    #         template=AvailableTemplate.NAME_UPDATE_SUCCESS,
    #         context_modules=context_modules,
    #         category=MessageCategory.SECURITY,
    #         default_channels=[MessageChannel.EMAIL]
    #     )
    #
    # async def send_2fa_message(self, recipient_user_id: MessageRecipientUserId,
    #                            context_modules:List[MessageContextModule]):
    #     await self._send_message(
    #         recipient_user_id=recipient_user_id,
    #         template=AvailableTemplate.TWO_FA,
    #         context_modules=context_modules,
    #         category=MessageCategory.SECURITY,
    #         default_channels=[
    #             MessageChannel.SMS,
    #             MessageChannel.EMAIL,
    #             MessageChannel.WHATSAPP
    #         ]
    #     )

    async def send_account_deactivation_message(self, recipient_user_id: MessageRecipientUserId,
                                                context_modules:List[MessageContextModule], extra_context: dict[MessageContext, Any]):
        await self._send_message(
            recipient_user_id=recipient_user_id,
            template=AvailableTemplate.ACCOUNT_DEACTIVATION,
            context_modules=context_modules,
            category=MessageCategory.ADMIN,
            default_channels=[
                MessageChannel.EMAIL
            ],
            extra_context=extra_context
        )

    async def send_account_activation_message(self, recipient_user_id: MessageRecipientUserId,
                                                context_modules:List[MessageContextModule], extra_context: dict[MessageContext, Any]):
        await self._send_message(
            recipient_user_id=recipient_user_id,
            template=AvailableTemplate.ACCOUNT_ACTIVATION,
            context_modules=context_modules,
            category=MessageCategory.ADMIN,
            default_channels=[
                MessageChannel.EMAIL
            ],
            extra_context=extra_context
        )
