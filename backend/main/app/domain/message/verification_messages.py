"""VerificationMessages — external channel dispatch for verification events (S39, S40)."""
from __future__ import annotations


from kink import inject

from main.app.domain.message.message_sender import BaseMessageSender
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.integrations.messaging.models import (
    EmailRecipient,
    MessageCategory,
    MessageChannel,
    MessageContext,
    MessageContextModule,
    MessageRecipientUserId,
    MessageRequestRecipient,
)
from main.appodus_utils.integrations.messaging.templating.models import AvailableTemplate


@inject
@decorate_all_methods(method_trace_logger, exclude=[""])
class VerificationMessages(BaseMessageSender):
    """External messaging for verification lifecycle events."""

    async def send_payment_confirmed(self, recipient_user_id: str) -> None:
        await self._send_message(
            recipient_user_id=MessageRecipientUserId(user_id=recipient_user_id),
            template=AvailableTemplate.VERIFICATION_PAYMENT_CONFIRMED,
            context_modules=[MessageContextModule.USER],
            category=MessageCategory.TRANSACTION,
            default_channels=[MessageChannel.EMAIL, MessageChannel.SMS],
        )

    async def send_report_ready(self, recipient_user_id: str) -> None:
        await self._send_message(
            recipient_user_id=MessageRecipientUserId(user_id=recipient_user_id),
            template=AvailableTemplate.VERIFICATION_REPORT_READY,
            context_modules=[MessageContextModule.USER],
            category=MessageCategory.TRANSACTION,
            default_channels=[MessageChannel.EMAIL, MessageChannel.SMS, MessageChannel.PUSH],
        )

    async def send_status_change(self, recipient_user_id: str, to_state: str) -> None:
        await self._send_message(
            recipient_user_id=MessageRecipientUserId(user_id=recipient_user_id),
            template=AvailableTemplate.VERIFICATION_STATUS_CHANGE,
            context_modules=[MessageContextModule.USER],
            category=MessageCategory.TRANSACTION,
            default_channels=[MessageChannel.EMAIL],
            extra_context={MessageContext.VERIFICATION_NEW_STATUS.value: to_state},
        )

    async def send_agents_assigned(self, recipient_user_id: str) -> None:
        await self._send_message(
            recipient_user_id=MessageRecipientUserId(user_id=recipient_user_id),
            template=AvailableTemplate.VERIFICATION_AGENTS_ASSIGNED,
            context_modules=[MessageContextModule.USER],
            category=MessageCategory.TRANSACTION,
            default_channels=[MessageChannel.EMAIL],
        )

    async def send_job_alert(self, recipient_user_id: str) -> None:
        await self._send_message(
            recipient_user_id=MessageRecipientUserId(user_id=recipient_user_id),
            template=AvailableTemplate.VERIFICATION_JOB_ALERT,
            context_modules=[MessageContextModule.USER],
            category=MessageCategory.TRANSACTION,
            default_channels=[MessageChannel.EMAIL, MessageChannel.SMS, MessageChannel.PUSH],
        )

    async def send_new_message_alert(self, recipient_user_id: str) -> None:
        await self._send_message(
            recipient_user_id=MessageRecipientUserId(user_id=recipient_user_id),
            template=AvailableTemplate.VERIFICATION_NEW_MESSAGE,
            context_modules=[MessageContextModule.USER],
            category=MessageCategory.TRANSACTION,
            default_channels=[MessageChannel.EMAIL],
        )

    async def send_sla_breach(self, recipient_user_id: str) -> None:
        await self._send_message(
            recipient_user_id=MessageRecipientUserId(user_id=recipient_user_id),
            template=AvailableTemplate.VERIFICATION_SLA_BREACH,
            context_modules=[MessageContextModule.USER],
            category=MessageCategory.TRANSACTION,
            default_channels=[MessageChannel.EMAIL, MessageChannel.SMS],
        )

    async def send_revision_request(self, recipient_user_id: str) -> None:
        await self._send_message(
            recipient_user_id=MessageRecipientUserId(user_id=recipient_user_id),
            template=AvailableTemplate.VERIFICATION_REVISION_REQUEST,
            context_modules=[MessageContextModule.USER],
            category=MessageCategory.TRANSACTION,
            default_channels=[MessageChannel.EMAIL],
        )

    async def send_recheck_decision(self, recipient_user_id: str, decision: str) -> None:
        await self._send_message(
            recipient_user_id=MessageRecipientUserId(user_id=recipient_user_id),
            template=AvailableTemplate.VERIFICATION_RECHECK_DECISION,
            context_modules=[MessageContextModule.USER],
            category=MessageCategory.TRANSACTION,
            default_channels=[MessageChannel.EMAIL],
            extra_context={MessageContext.RECHECK_DECISION_OUTCOME.value: decision},
        )

    async def send_dispute_filed(self, recipient_user_id: str, vid: str) -> None:
        await self._send_message(
            recipient_user_id=MessageRecipientUserId(user_id=recipient_user_id),
            template=AvailableTemplate.VERIFICATION_DISPUTE_FILED,
            context_modules=[MessageContextModule.USER],
            category=MessageCategory.TRANSACTION,
            default_channels=[MessageChannel.EMAIL],
            extra_context={MessageContext.DISPUTE_VERIFICATION_ID.value: vid},
        )

    async def send_dispute_resolved(self, recipient_user_id: str, outcome: str) -> None:
        await self._send_message(
            recipient_user_id=MessageRecipientUserId(user_id=recipient_user_id),
            template=AvailableTemplate.VERIFICATION_DISPUTE_RESOLVED,
            context_modules=[MessageContextModule.USER],
            category=MessageCategory.TRANSACTION,
            default_channels=[MessageChannel.EMAIL],
            extra_context={MessageContext.DISPUTE_RESOLUTION_OUTCOME.value: outcome},
        )

    async def send_report_share(self, recipient_email: str, vid: str, share_url: str) -> None:
        """Email a tokenised report link to a named recipient (§13.2). The recipient need
        not be a registered user, so the message goes to a raw email address."""
        recipient = MessageRequestRecipient(
            email=EmailRecipient(email=recipient_email),
        )
        await self._send_direct_message(
            recipient=recipient,
            template=AvailableTemplate.VERIFICATION_REPORT_SHARE,
            context={
                MessageContext.SHARE_VID.value: vid,
                MessageContext.SHARE_URL.value: share_url,
            },
            category=MessageCategory.TRANSACTION,
            default_channels=[MessageChannel.EMAIL],
        )

    async def send_payout_approved(self, recipient_user_id: str) -> None:
        await self._send_message(
            recipient_user_id=MessageRecipientUserId(user_id=recipient_user_id),
            template=AvailableTemplate.VERIFICATION_PAYOUT_APPROVED,
            context_modules=[MessageContextModule.USER],
            category=MessageCategory.TRANSACTION,
            default_channels=[MessageChannel.EMAIL],
        )

    async def send_payout_held(self, recipient_user_id: str, reason: str) -> None:
        await self._send_message(
            recipient_user_id=MessageRecipientUserId(user_id=recipient_user_id),
            template=AvailableTemplate.VERIFICATION_PAYOUT_HELD,
            context_modules=[MessageContextModule.USER],
            category=MessageCategory.TRANSACTION,
            default_channels=[MessageChannel.EMAIL],
            extra_context={MessageContext.PAYOUT_HOLD_REASON.value: reason},
        )

    async def send_abandonment_recovery(
        self,
        recipient_user_id: str,
        verification_id: str,
        vid: str,
    ) -> None:
        """One-time recovery email sent 24 hrs after wizard abandonment without payment."""
        await self._send_message(
            recipient_user_id=MessageRecipientUserId(user_id=recipient_user_id),
            template=AvailableTemplate.VERIFICATION_ABANDONMENT_RECOVERY,
            context_modules=[MessageContextModule.USER],
            category=MessageCategory.TRANSACTION,
            default_channels=[MessageChannel.EMAIL],
            extra_context={MessageContext.ABANDONMENT_VID.value: vid},
        )
