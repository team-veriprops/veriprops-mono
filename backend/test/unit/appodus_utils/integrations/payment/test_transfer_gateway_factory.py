"""Which gateway a payout leaves through.

A bank code is only meaningful to the gateway whose list it came from (Paystack and
Flutterwave number some fintech banks differently), so a payout goes out through the
platform its account was resolved with — and under PAYMENT_STUB_MODE, through the stub
whatever the account says, so a CI run can never reach a live gateway.
"""
import pytest

from main.app.config.settings import IntegratedPlatform, PaymentMethod, settings
from main.appodus_utils.integrations.exception.exceptions import IntegrationFatalException
from main.appodus_utils.integrations.factory import PaymentGatewayFactory
from main.appodus_utils.integrations.payment.gateway.flutterwave.payment import FlutterwavePaymentGateway
from main.appodus_utils.integrations.payment.gateway.paystack.payment import PaystackPaymentGateway
from main.appodus_utils.integrations.payment.gateway.stub import StubTransferGateway


@pytest.fixture
def factory():
    return PaymentGatewayFactory([FlutterwavePaymentGateway(), PaystackPaymentGateway()])


class TestTransferGateway:
    def test_stub_mode_always_pays_through_the_stub(self, monkeypatch, factory):
        monkeypatch.setattr(settings, "PAYMENT_STUB_MODE", True)

        assert isinstance(factory.transfers(IntegratedPlatform.PAYSTACK), StubTransferGateway)
        assert isinstance(factory.transfers(None), StubTransferGateway)
        assert factory.transfer_platform() is None

    def test_live_mode_pays_through_the_accounts_own_gateway(self, monkeypatch, factory):
        monkeypatch.setattr(settings, "PAYMENT_STUB_MODE", False)
        monkeypatch.setattr(settings, "ACTIVE_PAYMENT_METHOD", PaymentMethod.FLUTTERWAVE)

        assert isinstance(factory.transfers(IntegratedPlatform.PAYSTACK), PaystackPaymentGateway)
        assert factory.transfer_platform() == IntegratedPlatform.FLUTTERWAVE

    def test_live_mode_refuses_an_account_no_gateway_resolved(self, monkeypatch, factory):
        # An account saved under the stub carries no platform; its bank code proves nothing.
        monkeypatch.setattr(settings, "PAYMENT_STUB_MODE", False)

        with pytest.raises(IntegrationFatalException):
            factory.transfers(None)
