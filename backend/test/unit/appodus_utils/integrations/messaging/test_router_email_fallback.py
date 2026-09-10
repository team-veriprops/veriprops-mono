"""MessageRouter provider-selection contract for the email channel.

Prod/staging email must pick Resend first, with Mailjet then AWS SES as automatic
fallbacks — this pins that ordering so a future edit to the routing rules can't
silently drop the fallback chain.
"""
from decimal import Decimal

from main.app.config.settings import settings
from main.app.domain.message.models import UpsertMessageDto
from main.appodus_utils.config.settings import Environment
from main.appodus_utils.db.types.money import Money, TransactionCurrency
from main.appodus_utils.integrations.messaging.models import (
    EmailPayloadRequest,
    MessageChannel,
    MessageProviderName,
    MessageRecipient,
    MessageRequest,
)
from main.appodus_utils.integrations.messaging.providers.models import IMessageProvider
from main.appodus_utils.integrations.messaging.router import MessageRouter


class _FakeEmailProvider(IMessageProvider):
    def __init__(self, provider_name: MessageProviderName):
        self._name = provider_name

    @property
    def name(self) -> MessageProviderName:
        return self._name

    @property
    def supported_channels(self):
        return [MessageChannel.EMAIL]

    async def get_cost(self, message_id: str) -> Money:
        return Money(value=Decimal("0.0"), currency=TransactionCurrency.NGN)

    async def send_message(self, message: UpsertMessageDto) -> UpsertMessageDto:
        return message

    async def get_message_status(self, message_id: str):
        return None


def _email_message() -> UpsertMessageDto:
    return UpsertMessageDto.from_request(
        MessageRequest(
            channel=MessageChannel.EMAIL,
            to=MessageRecipient(recipient="user@example.com", fullname="Ada QA"),
            payload=EmailPayloadRequest(subject="Hello", html="<p>Hi</p>"),
            extras={"user_id": "u-1"},
        )
    )


def _router() -> MessageRouter:
    providers = [
        _FakeEmailProvider(MessageProviderName.SMTP),
        _FakeEmailProvider(MessageProviderName.RESEND),
        _FakeEmailProvider(MessageProviderName.MAILJET),
        _FakeEmailProvider(MessageProviderName.AWS_SES),
    ]
    return MessageRouter(providers=providers)


def test_prod_email_rule_prioritises_resend_then_mailjet_then_ses(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", Environment.PRODUCTION)
    router = _router()

    selected = router._select_provider(_email_message())

    assert selected.name == MessageProviderName.RESEND

    matched_rule = next(
        rule for rule in router.routing_rules["email"]["rules"]
        if MessageProviderName.RESEND in rule["providers"]
    )
    assert matched_rule["fallback_order"] == [
        MessageProviderName.RESEND,
        MessageProviderName.MAILJET,
        MessageProviderName.AWS_SES,
    ]


def test_staging_email_rule_also_prioritises_resend(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", Environment.STAGING)
    router = _router()

    selected = router._select_provider(_email_message())

    assert selected.name == MessageProviderName.RESEND
