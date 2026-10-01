"""MessageRouter provider-selection contract for the SMS channel.

Staging and production send real SMS, and every OTP fallback depends on this routing:
a Nigerian (+234) number goes to Termii with Twilio as the fallback, a HIGH-priority
foreign number goes to Twilio, and test/dev environments stay on the mock provider.
The rule conditions run on every send, so a condition that raises takes down SMS entirely.
"""
from decimal import Decimal

import pytest

from main.app.config.settings import settings
from main.app.domain.message.models import UpsertMessageDto
from main.appodus_utils.config.settings import Environment
from main.appodus_utils.db.types.money import Money, TransactionCurrency
from main.appodus_utils.integrations.exception.exceptions import (
    IntegrationException,
    IntegrationFatalException,
)
from main.appodus_utils.integrations.messaging.models import (
    MessageChannel,
    MessagePriority,
    MessageProviderName,
    MessageRecipient,
    MessageRequest,
    MessageStatus,
    SmsPayload,
)
from main.appodus_utils.integrations.messaging.providers.models import IMessageProvider
from main.appodus_utils.integrations.messaging.router import MessageRouter
from main.appodus_utils.integrations.messaging.services.resilience import resilience_manager

NIGERIAN_NUMBER = "+2348031234567"
UK_NUMBER = "+447700900123"


class _FakeSmsProvider(IMessageProvider):
    def __init__(self, provider_name: MessageProviderName, *, fails: bool = False):
        self._name = provider_name
        self._fails = fails
        self.sent: list[UpsertMessageDto] = []

    @property
    def name(self) -> MessageProviderName:
        return self._name

    @property
    def supported_channels(self):
        return [MessageChannel.SMS]

    async def get_cost(self, message_id: str) -> Money:
        return Money(value=Decimal("0.0"), currency=TransactionCurrency.NGN)

    async def send_message(self, message: UpsertMessageDto) -> UpsertMessageDto:
        if self._fails:
            raise IntegrationException(f"{self._name} is down")
        self.sent.append(message)
        message.provider = self._name
        message.status = MessageStatus.SENT
        return message

    async def get_message_status(self, message_id: str):
        return None


def _sms(recipient, priority: MessagePriority = MessagePriority.NORMAL) -> UpsertMessageDto:
    return UpsertMessageDto.from_request(
        MessageRequest(
            channel=MessageChannel.SMS,
            to=MessageRecipient(recipient=recipient),
            priority=priority,
            payload=SmsPayload(text="Your verification code is 123456"),
            extras={"user_id": "u-1"},
        )
    )


def _router(*, termii_fails: bool = False, twilio_fails: bool = False) -> tuple[MessageRouter, dict]:
    # Every provider is registered in every environment, the mock included — which is
    # why no live path may ever reach it by default or as a last resort.
    providers = {
        MessageProviderName.MOCK_SMS: _FakeSmsProvider(MessageProviderName.MOCK_SMS),
        MessageProviderName.TERMII_SMS: _FakeSmsProvider(MessageProviderName.TERMII_SMS, fails=termii_fails),
        MessageProviderName.TWILIO_SMS: _FakeSmsProvider(MessageProviderName.TWILIO_SMS, fails=twilio_fails),
    }
    return MessageRouter(providers=list(providers.values())), providers


@pytest.fixture(autouse=True)
def open_circuits(monkeypatch) -> set:
    """Routing in isolation from the resilience layer.

    Retries, backoff and the process-wide breakers are replaced with pass-through decorators,
    so a failing fake fails at once and leaves no breaker open for later tests. A test opens a
    provider's circuit by adding its name to the returned set.
    """
    opened: set = set()
    passthrough = lambda *args, **kwargs: (lambda fn: fn)  # noqa: E731
    monkeypatch.setattr(resilience_manager, "messaging_retry", passthrough)
    monkeypatch.setattr(resilience_manager, "messaging_circuit_breaker", passthrough)
    monkeypatch.setattr(resilience_manager, "get_circuit_state", lambda name: {"open": name in opened})
    return opened


@pytest.mark.parametrize("environment", [Environment.PRODUCTION, Environment.STAGING])
def test_a_nigerian_number_goes_to_termii(monkeypatch, environment):
    monkeypatch.setattr(settings, "ENVIRONMENT", environment)
    router, _ = _router()

    assert router._select_provider(_sms(NIGERIAN_NUMBER)).name == MessageProviderName.TERMII_SMS


@pytest.mark.parametrize("environment", [Environment.PRODUCTION, Environment.STAGING])
def test_a_high_priority_foreign_number_goes_to_twilio(monkeypatch, environment):
    monkeypatch.setattr(settings, "ENVIRONMENT", environment)
    router, _ = _router()

    selected = router._select_provider(_sms(UK_NUMBER, MessagePriority.HIGH))

    assert selected.name == MessageProviderName.TWILIO_SMS


def test_a_normal_priority_foreign_number_uses_the_channel_default_and_never_the_mock(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", Environment.PRODUCTION)
    router, _ = _router()

    selected = router._select_provider(_sms(UK_NUMBER))

    assert selected.name == MessageProviderName.TWILIO_SMS


@pytest.mark.parametrize(
    "environment", [Environment.TEST, Environment.DEVELOPMENT, Environment.DEV_PERSONAL]
)
def test_non_live_environments_never_leave_the_mock_provider(monkeypatch, environment):
    monkeypatch.setattr(settings, "ENVIRONMENT", environment)
    router, _ = _router()

    assert router._select_provider(_sms(NIGERIAN_NUMBER)).name == MessageProviderName.MOCK_SMS


def test_an_open_mock_circuit_never_lets_a_test_run_reach_a_real_provider(monkeypatch, open_circuits):
    """An exclusive rule stays exclusive when its provider's circuit is open: the send fails
    on that provider rather than falling through to Termii or Twilio."""
    monkeypatch.setattr(settings, "ENVIRONMENT", Environment.TEST)
    open_circuits.add(MessageProviderName.MOCK_SMS)
    router, _ = _router()

    assert router._select_provider(_sms(NIGERIAN_NUMBER)).name == MessageProviderName.MOCK_SMS


def test_a_single_recipient_given_as_a_list_is_still_routed_by_its_number(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", Environment.PRODUCTION)
    router, _ = _router()

    assert router._select_provider(_sms([NIGERIAN_NUMBER])).name == MessageProviderName.TERMII_SMS


async def test_a_termii_outage_falls_back_to_twilio(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", Environment.PRODUCTION)
    router, providers = _router(termii_fails=True)

    result = await router.send_message(_sms(NIGERIAN_NUMBER))

    assert result.provider == MessageProviderName.TWILIO_SMS
    assert len(providers[MessageProviderName.TWILIO_SMS].sent) == 1


async def test_when_every_live_provider_is_down_the_send_fails_instead_of_reaching_the_mock(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", Environment.PRODUCTION)
    router, providers = _router(termii_fails=True, twilio_fails=True)

    with pytest.raises(IntegrationFatalException):
        await router.send_message(_sms(NIGERIAN_NUMBER))

    assert providers[MessageProviderName.MOCK_SMS].sent == []
