"""FirebasePushProvider credential handling.

The message router constructs every provider when messaging first loads, so the Firebase
provider must build without credentials. Push has no registered device tokens yet (§G), and
a missing key has to surface on a push send, never on an unrelated email or SMS.
"""
import pytest

from main.app.config.settings import settings
from main.appodus_utils.integrations.exception.exceptions import IntegrationFatalException
from main.appodus_utils.integrations.messaging.models import (
    MessageChannel,
    MessageRecipient,
    MessageRequest,
    PushPayload,
)
from main.app.domain.message.models import UpsertMessageDto
from main.appodus_utils.integrations.messaging.providers.push import firebase as firebase_module
from main.appodus_utils.integrations.messaging.providers.push.firebase import FirebasePushProvider


@pytest.fixture
def unconfigured(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "FIREBASE_CREDENTIALS_JSON_B64", None)
    monkeypatch.setattr(settings, "FIREBASE_CREDENTIALS_PATH", str(tmp_path / "missing.json"))
    monkeypatch.setattr(firebase_module.firebase_admin, "_apps", {})


def test_the_provider_builds_without_credentials(unconfigured):
    FirebasePushProvider()


async def test_a_push_send_without_credentials_fails_as_not_configured(unconfigured):
    provider = FirebasePushProvider()
    message = UpsertMessageDto.from_request(MessageRequest(
        channel=MessageChannel.PUSH,
        to=MessageRecipient(recipient="device-token"),
        payload=PushPayload(title="Hello", body="World"),
        extras={"user_id": "u-1"},
    ))

    with pytest.raises(IntegrationFatalException):
        await provider.send_message(message)


async def test_a_malformed_secret_fails_as_not_configured(unconfigured, monkeypatch):
    monkeypatch.setattr(settings, "FIREBASE_CREDENTIALS_JSON_B64", "bm90LWpzb24=")

    with pytest.raises(IntegrationFatalException):
        FirebasePushProvider._ensure_app()
