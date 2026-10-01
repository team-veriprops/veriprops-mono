"""QA fixtures never reach a live provider.

`/dev/seed` and `/dev/scenario` run on staging too, where email and SMS go out through real
providers — and the people they create need contact details. A fixture's email and phone
therefore come from ranges the router recognises, and on staging a message to one of them is
recorded by the QA sink instead of being sent. Anyone else on staging (human QA's own phones)
is untouched, and production has no fixtures and no sink.
"""
from decimal import Decimal

import pytest

from main.app.config.settings import settings
from main.app.domain.message.models import UpsertMessageDto
from main.appodus_utils.config.settings import Environment
from main.appodus_utils.db.types.money import Money, TransactionCurrency
from main.appodus_utils.integrations.messaging.models import (
    EmailPayload,
    MessageChannel,
    MessageProviderName,
    MessageRecipient,
    MessageStatus,
    SmsPayload,
)
from main.appodus_utils.integrations.messaging.providers.models import IMessageProvider
from main.appodus_utils.integrations.messaging.providers.qa_sink import QaSinkProvider
from main.appodus_utils.integrations.messaging.qa_recipients import (
    QA_EMAIL_DOMAIN,
    is_qa_recipient,
    qa_local_phone,
    unique_qa_local_phone,
)
from main.appodus_utils.integrations.messaging.router import MessageRouter
from main.appodus_utils.integrations.messaging.services.resilience import resilience_manager

QA_PHONE = f"+234{qa_local_phone(1)}"
REAL_PHONE = "+2348031234567"
QA_EMAIL = f"qa-scn-customer-1a2b@{QA_EMAIL_DOMAIN}"
REAL_EMAIL = "tester@example.com"


class TestRecognisingAFixture:
    def test_fixture_phones_share_one_recognisable_range(self):
        for _ in range(50):
            assert is_qa_recipient(MessageChannel.SMS, f"+234{unique_qa_local_phone()}")
        assert is_qa_recipient(MessageChannel.SMS, QA_PHONE)

    def test_a_whatsapp_number_is_digits_only(self):
        assert is_qa_recipient(MessageChannel.WHATSAPP, QA_PHONE.lstrip("+"))

    def test_fixture_emails_are_recognised_by_domain_in_any_case(self):
        assert is_qa_recipient(MessageChannel.EMAIL, QA_EMAIL.upper())

    @pytest.mark.parametrize("channel, recipient", [
        (MessageChannel.SMS, REAL_PHONE),
        (MessageChannel.EMAIL, REAL_EMAIL),
        (MessageChannel.EMAIL, f"someone@not{QA_EMAIL_DOMAIN}"),
    ])
    def test_anyone_else_is_not_a_fixture(self, channel, recipient):
        assert not is_qa_recipient(channel, recipient)


class _Fake(IMessageProvider):
    def __init__(self, name: MessageProviderName, channels):
        self._name, self._channels = name, channels

    @property
    def name(self):
        return self._name

    @property
    def supported_channels(self):
        return self._channels

    async def get_cost(self, message_id: str) -> Money:
        return Money(value=Decimal("0"), currency=TransactionCurrency.NGN)

    async def send_message(self, message):
        return message

    async def get_message_status(self, message_id: str):
        return None


def _router() -> MessageRouter:
    sms, email = [MessageChannel.SMS], [MessageChannel.EMAIL]
    return MessageRouter(providers=[
        _Fake(MessageProviderName.MOCK_SMS, sms),
        _Fake(MessageProviderName.TERMII_SMS, sms),
        _Fake(MessageProviderName.TWILIO_SMS, sms),
        _Fake(MessageProviderName.SMTP, email),
        _Fake(MessageProviderName.RESEND, email),
        _Fake(MessageProviderName.MAILJET, email),
        _Fake(MessageProviderName.AWS_SES, email),
        _Fake(MessageProviderName.QA_SINK, [MessageChannel.SMS, MessageChannel.EMAIL]),
    ])


def _sms(to: str) -> UpsertMessageDto:
    return UpsertMessageDto(channel=MessageChannel.SMS, to=MessageRecipient(recipient=to),
                            payload=SmsPayload(text="Your code is 123456"))


def _email(to: str) -> UpsertMessageDto:
    return UpsertMessageDto(channel=MessageChannel.EMAIL, to=MessageRecipient(recipient=to),
                            payload=EmailPayload(subject="Hello", text="Hello"))


@pytest.fixture(autouse=True)
def closed_circuits(monkeypatch):
    monkeypatch.setattr(resilience_manager, "get_circuit_state", lambda name: {"open": False})


class TestRouting:
    def test_on_staging_a_fixture_is_sunk_on_every_channel(self, monkeypatch):
        monkeypatch.setattr(settings, "ENVIRONMENT", Environment.STAGING)
        router = _router()

        assert router._select_provider(_sms(QA_PHONE)).name == MessageProviderName.QA_SINK
        assert router._select_provider(_email(QA_EMAIL)).name == MessageProviderName.QA_SINK

    def test_on_staging_everyone_else_still_goes_live(self, monkeypatch):
        monkeypatch.setattr(settings, "ENVIRONMENT", Environment.STAGING)
        router = _router()

        assert router._select_provider(_sms(REAL_PHONE)).name == MessageProviderName.TERMII_SMS
        assert router._select_provider(_email(REAL_EMAIL)).name == MessageProviderName.RESEND

    @pytest.mark.parametrize("environment", [Environment.TEST, Environment.DEVELOPMENT, Environment.DEV_PERSONAL])
    def test_locally_fixtures_keep_their_mailpit_and_mock_routes(self, monkeypatch, environment):
        """The e2e suite reads fixture mail from Mailpit, so the sink is staging's alone."""
        monkeypatch.setattr(settings, "ENVIRONMENT", environment)
        router = _router()

        assert router._select_provider(_sms(QA_PHONE)).name == MessageProviderName.MOCK_SMS
        assert router._select_provider(_email(QA_EMAIL)).name == MessageProviderName.SMTP

    def test_production_never_sinks(self, monkeypatch):
        monkeypatch.setattr(settings, "ENVIRONMENT", Environment.PRODUCTION)
        router = _router()

        assert router._select_provider(_sms(QA_PHONE)).name == MessageProviderName.TERMII_SMS


class TestTheSink:
    async def test_it_records_the_message_as_sent_without_sending(self, monkeypatch):
        monkeypatch.setattr(settings, "ENVIRONMENT", Environment.STAGING)

        sent = await QaSinkProvider().send_message(_sms(QA_PHONE))

        assert sent.status == MessageStatus.SENT
        assert sent.provider == MessageProviderName.QA_SINK
        assert sent.provider_id

    async def test_it_refuses_production(self, monkeypatch):
        monkeypatch.setattr(settings, "ENVIRONMENT", Environment.PRODUCTION)

        with pytest.raises(ValueError):
            await QaSinkProvider().send_message(_sms(QA_PHONE))
