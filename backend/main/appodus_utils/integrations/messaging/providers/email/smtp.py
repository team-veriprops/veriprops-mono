from __future__ import annotations

import asyncio
import smtplib
from decimal import Decimal
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List

from kink import di

from main.app.config.settings import settings
from main.app.domain.message.models import UpsertMessageDto
from main.appodus_utils.db.types.money import Money, TransactionCurrency
from main.appodus_utils.integrations.messaging.models import (
    MessageChannel,
    MessageProviderName,
    MessageStatus,
)
from main.appodus_utils.integrations.messaging.providers.models import IMessageProvider
from main.appodus_utils.config.settings import Environment
from main.appodus_utils import Utils

logger = di["logger"]


class SmtpEmailProvider(IMessageProvider):
    """Local SMTP email provider for dev/test environments (Mailpit).

    Connects to settings.SMTP_HOST:SMTP_PORT via smtplib (no auth required
    for Mailpit). The synchronous smtplib call runs in a thread-pool executor
    so it does not block the event loop.

    Hard-fails with ValueError in production or staging — never commit emails
    via SMTP in those environments.
    """

    @property
    def name(self) -> MessageProviderName:
        return MessageProviderName.SMTP

    @property
    def supported_channels(self) -> List[MessageChannel]:
        return [MessageChannel.EMAIL]

    async def get_cost(self, message_id: str) -> Money:
        return Money(value=Decimal("0.0"), currency=TransactionCurrency.NGN)

    async def get_message_status(self, message_id: str) -> Dict[str, Any]:
        return {}

    async def send_message(self, message: UpsertMessageDto) -> UpsertMessageDto:
        env = settings.ENVIRONMENT
        if env in {Environment.PRODUCTION, Environment.STAGING}:
            raise ValueError(
                "SmtpEmailProvider must not be used in production or staging. "
                f"Current environment: {env}"
            )

        payload = message.payload
        recipient = message.to

        to_addresses: List[str] = (
            recipient.recipient
            if isinstance(recipient.recipient, list)
            else [recipient.recipient]
        )

        from_email = getattr(payload, "from_email", None) or settings.EMAIL_FROM_ADDRESS
        from_name = getattr(payload, "from_name", None) or settings.EMAIL_FROM_NAME
        subject = payload.subject

        mime_msg = MIMEMultipart("alternative")
        mime_msg["Subject"] = subject
        mime_msg["From"] = f"{from_name} <{from_email}>"
        mime_msg["To"] = ", ".join(to_addresses)

        if getattr(payload, "reply_to", None):
            mime_msg["Reply-To"] = payload.reply_to

        if getattr(payload, "text", None):
            mime_msg.attach(MIMEText(payload.text, "plain", "utf-8"))
        if getattr(payload, "html", None):
            mime_msg.attach(MIMEText(payload.html, "html", "utf-8"))

        host = settings.SMTP_HOST
        port = settings.SMTP_PORT
        use_tls = settings.SMTP_USE_TLS
        username = settings.SMTP_USERNAME
        password = settings.SMTP_PASSWORD
        raw = mime_msg.as_string()

        def _send_sync() -> None:
            with smtplib.SMTP(host, port) as server:
                if use_tls:
                    server.starttls()
                if username and password:
                    server.login(username, password)
                server.sendmail(from_email, to_addresses, raw)

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _send_sync)

        logger.debug(
            "SMTP email sent to %s via %s:%s (subject: %s)",
            to_addresses, host, port, subject,
        )

        message.sent_at = Utils.datetime_now()
        message.provider = self.name
        message.status = MessageStatus.SENT
        return message
