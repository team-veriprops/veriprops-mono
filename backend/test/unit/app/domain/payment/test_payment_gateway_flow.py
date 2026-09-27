"""PaymentService on the live-gateway path (PAYMENT_STUB_MODE=false) — gateway and repos mocked.

The rules pinned here are the money rules:

* a live payment opens the active gateway's hosted checkout for exactly what the customer was
  quoted, and the stub path never touches a gateway;
* a payment is settled only from the gateway's own answer, and only when that answer matches
  the reference, amount and currency Veriprops asked for — a webhook alone never pays;
* a pending or unknown charge, a settled payment and a stub payment are all left alone;
* a chargeback is matched to its payment by our reference or by the gateway's.
"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.config.settings import IntegratedPlatform, settings
from main.app.core.state.status import VerificationStatus
from main.app.domain.audit.models import AuditActionType
from main.app.domain.payment.models import (
    PaymentMethodKind,
    PaymentPurpose,
    PaymentStatus,
    PaymentWebhookDto,
)
from main.app.domain.payment.service import PaymentService
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.db.types.money import TransactionCurrency
from main.appodus_utils.integrations.exception.exceptions import IntegrationException
from main.appodus_utils.integrations.payment.gateway.models import GatewayCharge, GatewayChargeStatus

TX_REF = "VP-2026-ABC123-x1y2z3w4"


@pytest.fixture(autouse=True)
def mock_db_session():
    session = MagicMock()
    session.in_transaction.return_value = False

    @asynccontextmanager
    async def _begin():
        yield

    session.begin = _begin
    session.flush = AsyncMock()
    token = db_session_ctx.set(session)
    yield session
    db_session_ctx.reset(token)


@pytest.fixture
def live(monkeypatch):
    monkeypatch.setattr(settings, "PAYMENT_STUB_MODE", False)
    monkeypatch.setattr(settings, "PUBLIC_APP_BASE_URL", "https://veriprops.ng")


@pytest.fixture
def stub(monkeypatch):
    monkeypatch.setattr(settings, "PAYMENT_STUB_MODE", True)


def _verification(**over):
    base = dict(
        id="ver-1", vid="VP-2026-ABC123", status=VerificationStatus.SUBMITTED.value, customer_id="cust-1",
        price_locked_minor=12_000_000, currency="NGN", charge_currency="USD", charge_amount_minor=8_000,
    )
    base.update(over)
    return SimpleNamespace(**base)


def _payment(**over):
    base = dict(
        id="pay-1", tx_ref=TX_REF, verification_id="ver-1", customer_id="cust-1",
        status=PaymentStatus.INITIATED.value, provider=IntegratedPlatform.FLUTTERWAVE.value,
        amount_minor=12_000_000, currency="NGN", charge_currency="USD", charge_amount_minor=8_000,
        gateway_reference=None, purpose=PaymentPurpose.INITIAL.value, checkout_url=None, chargeback_status=None,
        date_created=datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc),
    )
    base.update(over)
    return SimpleNamespace(**base)


def _charge(**over) -> GatewayCharge:
    base = dict(
        reference=TX_REF, gateway_transaction_id="3091255", gateway_reference="FLW-MOCK-1",
        status=GatewayChargeStatus.SUCCEEDED, amount_minor=8_000, currency=TransactionCurrency.USD,
    )
    base.update(over)
    return GatewayCharge(**base)


def _service(payment=None, charge=None):
    svc = object.__new__(PaymentService)
    svc._payment_repo = MagicMock()
    svc._verification_service = MagicMock()
    svc._task_service = MagicMock()
    svc._user_service = MagicMock()
    svc._idempotency = MagicMock()
    svc._audit = MagicMock()

    svc._verification_service.get_owned = AsyncMock(return_value=_verification())
    svc._verification_service.get_by_id = AsyncMock(return_value=_verification())
    svc._verification_service.mark_payment_pending = AsyncMock()
    svc._idempotency.claim = AsyncMock(return_value=True)
    svc._user_service.get_user_model = AsyncMock(return_value=SimpleNamespace(
        phone_verified=True, email="ada@example.com", phone="+2348031234567", first_name="Ada", last_name="Obi",
    ))
    def _create(dto):
        # The row the repo would return: exactly what the service asked to store.
        row = SimpleNamespace(id="pay-new", **dto.model_dump(by_alias=False))
        for enum_field in ("method", "purpose", "status", "currency", "charge_currency"):
            value = getattr(row, enum_field, None)
            if value is not None and hasattr(value, "value"):
                setattr(row, enum_field, value.value)
        svc._created = row
        return row

    created = _payment(checkout_url=None)
    svc._payment_repo.create_return_model = AsyncMock(side_effect=_create)
    svc._payment_repo.update = AsyncMock()
    svc._payment_repo.get_by_tx_ref = AsyncMock(return_value=payment)
    svc._payment_repo.get_model = AsyncMock(return_value=payment or created)

    gateway = MagicMock()
    gateway.platform = IntegratedPlatform.FLUTTERWAVE
    gateway.create_hosted_checkout = AsyncMock(return_value="https://checkout.flutterwave.com/v3/hosted/pay/abc")
    gateway.get_charge = AsyncMock(return_value=charge)
    svc._gateways = MagicMock()
    svc._gateways.active = MagicMock(return_value=gateway)
    svc._gateways.for_platform = MagicMock(return_value=gateway)
    svc._gateway = gateway
    return svc


class TestInitiateLive:
    async def test_opens_the_active_gateways_checkout_for_the_quoted_charge(self, live):
        svc = _service()

        payment = await svc.initiate("ver-1", "cust-1", PaymentMethodKind.CARD)

        request = svc._gateway.create_hosted_checkout.await_args.args[0]
        # The customer pays what they were quoted, in the currency they were quoted it.
        assert request.amount_minor == 8_000
        assert request.currency == TransactionCurrency.USD
        assert request.reference == svc._payment_repo.create_return_model.await_args.args[0].tx_ref
        assert request.redirect_url == "https://veriprops.ng/portal/verifications/ver-1/pay"
        assert request.customer_email == "ada@example.com"
        assert request.customer_name == "Ada Obi"
        assert svc._payment_repo.create_return_model.await_args.args[0].provider == IntegratedPlatform.FLUTTERWAVE.value
        assert payment.checkout_url == "https://checkout.flutterwave.com/v3/hosted/pay/abc"
        assert svc._payment_repo.update.await_args.args[1].checkout_url == payment.checkout_url

    async def test_a_gateway_that_cannot_open_a_checkout_fails_the_initiation(self, live):
        svc = _service()
        svc._gateway.create_hosted_checkout = AsyncMock(side_effect=IntegrationException("Could not open the checkout."))

        with pytest.raises(IntegrationException):
            await svc.initiate("ver-1", "cust-1", PaymentMethodKind.CARD)

    async def test_a_secondary_charge_opens_a_checkout_too(self, live):
        svc = _service()

        await svc.initiate_secondary("ver-1", "cust-1", 500_000, PaymentPurpose.RECHECK)

        request = svc._gateway.create_hosted_checkout.await_args.args[0]
        assert request.amount_minor == 500_000
        assert request.currency == TransactionCurrency.NGN


class TestInitiateStub:
    async def test_the_stub_path_never_touches_a_gateway(self, stub):
        svc = _service()

        await svc.initiate("ver-1", "cust-1", PaymentMethodKind.CARD)

        svc._gateways.active.assert_not_called()
        dto = svc._payment_repo.create_return_model.await_args.args[0]
        assert dto.provider is None
        assert dto.checkout_url.endswith("stub=1")


class TestConfirmFromGateway:
    async def test_a_matching_success_settles_through_the_idempotent_webhook(self, live):
        svc = _service(payment=_payment(), charge=_charge())
        svc.handle_webhook = AsyncMock(return_value=True)

        assert await svc.confirm_from_gateway(TX_REF) is True

        dto: PaymentWebhookDto = svc.handle_webhook.await_args.args[0]
        assert dto.succeeded is True
        assert dto.tx_ref == TX_REF
        assert dto.event_id == "flutterwave:3091255:SUCCEEDED"
        svc._gateways.for_platform.assert_called_once_with(IntegratedPlatform.FLUTTERWAVE)
        assert svc._payment_repo.update.await_args.args[1].gateway_reference == "FLW-MOCK-1"

    async def test_a_failed_charge_is_recorded_as_a_failure(self, live):
        svc = _service(payment=_payment(), charge=_charge(status=GatewayChargeStatus.FAILED))
        svc.handle_webhook = AsyncMock(return_value=True)

        await svc.confirm_from_gateway(TX_REF)

        assert svc.handle_webhook.await_args.args[0].succeeded is False

    @pytest.mark.parametrize("mismatch", [
        {"amount_minor": 7_999},
        {"currency": TransactionCurrency.NGN},
        {"reference": "someone-elses-ref"},
    ])
    async def test_a_charge_that_does_not_match_the_quote_never_pays(self, live, mismatch):
        svc = _service(payment=_payment(), charge=_charge(**mismatch))
        svc.handle_webhook = AsyncMock()

        assert await svc.confirm_from_gateway(TX_REF) is False

        svc.handle_webhook.assert_not_awaited()
        assert svc._audit.schedule.call_args.kwargs["action"] == AuditActionType.PAYMENT_AMOUNT_MISMATCH

    @pytest.mark.parametrize("charge", [None, "pending"])
    async def test_an_unsettled_or_unknown_charge_is_left_alone(self, live, charge):
        svc = _service(payment=_payment(), charge=_charge(status=GatewayChargeStatus.PENDING) if charge else None)
        svc.handle_webhook = AsyncMock()

        assert await svc.confirm_from_gateway(TX_REF) is False
        svc.handle_webhook.assert_not_awaited()

    async def test_a_settled_payment_is_not_asked_about_again(self, live):
        svc = _service(payment=_payment(status=PaymentStatus.SUCCEEDED.value), charge=_charge())

        assert await svc.confirm_from_gateway(TX_REF) is False
        svc._gateway.get_charge.assert_not_awaited()

    async def test_a_stub_payment_has_no_gateway_to_ask(self, live):
        svc = _service(payment=_payment(provider=None), charge=_charge())

        assert await svc.confirm_from_gateway(TX_REF) is False
        svc._gateway.get_charge.assert_not_awaited()

    async def test_a_reference_we_never_issued_is_ignored(self, live):
        svc = _service(payment=None, charge=_charge())

        assert await svc.confirm_from_gateway("not-ours") is False
        svc._gateway.get_charge.assert_not_awaited()


class TestReconcile:
    async def test_it_asks_the_gateway_about_the_customers_open_payments(self, live):
        svc = _service(payment=_payment())
        svc._payment_repo.list_for_verification = AsyncMock(return_value=[
            _payment(), _payment(id="pay-0", tx_ref="old", status=PaymentStatus.SUCCEEDED.value),
        ])
        svc.confirm_from_gateway = AsyncMock(return_value=True)

        await svc.reconcile_for_verification("ver-1", "cust-1")

        svc._verification_service.get_owned.assert_awaited_once_with("ver-1", "cust-1")
        svc.confirm_from_gateway.assert_awaited_once_with(TX_REF)

    async def test_the_stub_path_asks_no_gateway(self, stub):
        svc = _service(payment=_payment())
        svc._payment_repo.list_for_verification = AsyncMock(return_value=[_payment()])
        svc.confirm_from_gateway = AsyncMock()

        await svc.reconcile_for_verification("ver-1", "cust-1")

        svc.confirm_from_gateway.assert_not_awaited()


class TestChargebackIntake:
    async def test_a_chargeback_citing_the_gateway_reference_reaches_the_chargeback_flow(self, live, monkeypatch):
        svc = _service()
        svc._payment_repo.get_by_gateway_reference = AsyncMock(return_value=_payment(gateway_reference="FLW-MOCK-1"))
        chargebacks = MagicMock()
        chargebacks.handle_webhook = AsyncMock(return_value="chargeback")
        monkeypatch.setattr(PaymentService, "_chargeback_service", staticmethod(lambda: chargebacks))

        result = await svc.record_chargeback(
            IntegratedPlatform.FLUTTERWAVE, event_id="flutterwave:chargeback:9",
            gateway_reference="FLW-MOCK-1", reason="fraudulent", amount_minor=8_000,
        )

        assert result == "chargeback"
        dto = chargebacks.handle_webhook.await_args.args[0]
        assert (dto.event_id, dto.tx_ref, dto.reason, dto.amount_minor) == (
            "flutterwave:chargeback:9", TX_REF, "fraudulent", 8_000,
        )
        svc._payment_repo.get_by_gateway_reference.assert_awaited_once_with("flutterwave", "FLW-MOCK-1")

    async def test_a_chargeback_for_a_payment_we_do_not_hold_is_ignored(self, live, monkeypatch):
        svc = _service()
        svc._payment_repo.get_by_tx_ref = AsyncMock(return_value=None)
        chargebacks = MagicMock()
        chargebacks.handle_webhook = AsyncMock()
        monkeypatch.setattr(PaymentService, "_chargeback_service", staticmethod(lambda: chargebacks))

        assert await svc.record_chargeback(
            IntegratedPlatform.PAYSTACK, event_id="paystack:dispute:1", tx_ref="not-ours",
        ) is None
        chargebacks.handle_webhook.assert_not_awaited()


class TestConfirmGuards:
    async def test_a_payment_under_a_chargeback_is_never_settled_again(self, live):
        svc = _service(payment=_payment(status=PaymentStatus.FAILED.value, chargeback_status="LOST"), charge=_charge())
        svc.handle_webhook = AsyncMock()

        assert await svc.confirm_from_gateway(TX_REF) is False
        svc._gateway.get_charge.assert_not_awaited()

    async def test_a_failed_payment_the_gateway_still_calls_failed_is_not_counted_again(self, live):
        svc = _service(payment=_payment(status=PaymentStatus.FAILED.value),
                       charge=_charge(status=GatewayChargeStatus.FAILED))
        svc.handle_webhook = AsyncMock()

        assert await svc.confirm_from_gateway(TX_REF) is False
        svc.handle_webhook.assert_not_awaited()

    async def test_a_failed_payment_the_customer_then_paid_settles(self, live):
        svc = _service(payment=_payment(status=PaymentStatus.FAILED.value), charge=_charge())
        svc.handle_webhook = AsyncMock(return_value=True)

        assert await svc.confirm_from_gateway(TX_REF) is True

    async def test_a_mismatch_is_audited_once_per_charge(self, live):
        svc = _service(payment=_payment(), charge=_charge(amount_minor=1))
        svc._idempotency.claim = AsyncMock(side_effect=[True, False])

        await svc.confirm_from_gateway(TX_REF)
        await svc.confirm_from_gateway(TX_REF)

        assert svc._audit.schedule.call_count == 1
        assert svc._idempotency.claim.await_args.args[0] == "flutterwave:3091255:MISMATCH"


class TestReconcileLatestOnly:
    async def test_only_the_latest_payment_is_asked_about(self, live):
        older = _payment(id="pay-0", tx_ref="old", date_created=datetime(2026, 9, 26, tzinfo=timezone.utc))
        svc = _service(payment=_payment())
        svc._payment_repo.list_for_verification = AsyncMock(return_value=[older, _payment()])
        svc.confirm_from_gateway = AsyncMock(return_value=False)

        await svc.reconcile_for_verification("ver-1", "cust-1")

        svc.confirm_from_gateway.assert_awaited_once_with(TX_REF)

    async def test_a_gateway_that_cannot_answer_leaves_the_payment_as_it_is(self, live):
        svc = _service(payment=_payment())
        svc._payment_repo.list_for_verification = AsyncMock(return_value=[_payment()])
        svc.confirm_from_gateway = AsyncMock(side_effect=IntegrationException("Could not check the payment."))

        payment = await svc.reconcile_for_verification("ver-1", "cust-1")

        assert payment.tx_ref == TX_REF


class TestReturnPath:
    async def test_a_caller_can_send_the_customer_back_somewhere_else(self, live):
        svc = _service()

        await svc.initiate("ver-1", "cust-1", PaymentMethodKind.CARD, return_path="/wa/pay/return")

        request = svc._gateway.create_hosted_checkout.await_args.args[0]
        assert request.redirect_url == "https://veriprops.ng/wa/pay/return"
