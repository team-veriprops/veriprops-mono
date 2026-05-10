"""Unit tests for PaymentService (S16 — R5.5–R5.13).

Covers:
- CARD initiation → Flutterwave checkout_url returned, provider_ref stored
- BANK_TRANSFER initiation → Paystack virtual account instructions returned
- WIRE initiation → SWIFT/IBAN from settings, uploadProofTo present
- record_provider_event SUCCEEDED → verification transitions to PAID
- Duplicate webhook for same provider_ref → idempotent (no double-transition)
- Wire-proof upload → PENDING_WIRE status set
- Admin confirm_wire → SUCCEEDED, triggers _on_payment_succeeded
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from main.app.domain.payment.models import (
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
    InitiatePaymentDto,
    WireProofDto,
    ConfirmWireDto,
    UpdatePaymentDto,
)
from main.app.domain.payment.service import PaymentService
from main.app.domain.verification.models import VerificationStatus
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import (
    InvalidResourceStateException,
    ResourceNotFoundException,
)
from main.app.config.settings import IntegratedPlatform

_NOW = datetime(2026, 5, 7, 12, 0, 0, tzinfo=timezone.utc)

_SNAPSHOT_JSON = json.dumps({
    "tier": "STANDARD",
    "currency": "NGN",
    "base_amount_minor": 34000000,
    "line_items": [],
    "total_amount_minor": 35000000,
    "fx_rate": None,
    "fx_stale": False,
    "locked_at": _NOW.isoformat(),
    "expires_at": _NOW.isoformat(),
})

_VID = "VP-2026-000001"
_PAYMENT_ID = "pay-uuid-0001"
_VERIFICATION_ID = "ver-uuid-0001"
_CUSTOMER_ID = "usr-uuid-0001"
_ADMIN_ID = "adm-uuid-0001"


def _make_verification(status=VerificationStatus.SUBMITTED.value, vid=_VID):
    return SimpleNamespace(
        id=_VERIFICATION_ID,
        customer_id=_CUSTOMER_ID,
        status=status,
        pricing_snapshot=_SNAPSHOT_JSON,
        vid=vid,
    )


def _make_payment(
    status=PaymentStatus.INITIATED.value,
    method=PaymentMethod.CARD.value,
    provider=PaymentProvider.FLUTTERWAVE.value,
    provider_ref=None,
):
    return SimpleNamespace(
        id=_PAYMENT_ID,
        verification_id=_VERIFICATION_ID,
        status=status,
        method=method,
        provider=provider,
        provider_ref=provider_ref,
        amount_minor=35000000,
        currency="NGN",
        failure_reason=None,
        wire_proof_url=None,
        date_created=_NOW,
        date_updated=_NOW,
    )


def _make_user():
    return SimpleNamespace(
        id=_CUSTOMER_ID,
        email="customer@example.com",
        first_name="Ada",
        last_name="Obi",
        phone="08012345678",
        phone_dial_code="+234",
        phone_e164="+2348012345678",
        trust_status=None,
    )


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


def _make_service(
    *,
    payment=None,
    verification=None,
    user=None,
    gateway_factory=None,
) -> PaymentService:
    payment_repo = MagicMock()
    payment_repo.create = AsyncMock()
    payment_repo.update = AsyncMock()
    payment_repo.get_model = AsyncMock(return_value=payment)
    payment_repo.get_by_provider_ref = AsyncMock(return_value=payment)

    page = MagicMock()
    page.items = [payment] if payment else []
    payment_repo.get_page = AsyncMock(return_value=page)

    attempt_repo = MagicMock()
    attempt_repo.create = AsyncMock()

    verification_repo = MagicMock()
    verification_repo.get_model = AsyncMock(return_value=verification)

    verification_service = MagicMock()
    verification_service.transition = AsyncMock()

    session_service = MagicMock()
    session_service.record_event = AsyncMock()

    user_repo = MagicMock()
    user_repo.get_model = AsyncMock(return_value=user or _make_user())
    user_repo.update = AsyncMock()

    if gateway_factory is None:
        gateway_factory = MagicMock()

    return PaymentService(
        payment_repo=payment_repo,
        attempt_repo=attempt_repo,
        verification_repo=verification_repo,
        verification_service=verification_service,
        session_service=session_service,
        user_repo=user_repo,
        gateway_factory=gateway_factory,
    )


# ── CARD initiation ────────────────────────────────────────────────


class TestInitiateCard:
    async def test_returns_checkout_url(self):
        verification = _make_verification()
        payment = _make_payment()
        flw_gw = MagicMock()
        flw_gw.initialize_payment = AsyncMock(return_value="https://checkout.flutterwave.com/abc")
        gw_factory = MagicMock()
        gw_factory.get_gateway = MagicMock(return_value=flw_gw)

        svc = _make_service(payment=payment, verification=verification, gateway_factory=gw_factory)
        dto = InitiatePaymentDto(
            verification_id=_VERIFICATION_ID, method=PaymentMethod.CARD, redirect_url="https://app.veriprops.ng/pay"
        )
        result = await svc.initiate(_CUSTOMER_ID, dto)

        assert result.checkout_url == "https://checkout.flutterwave.com/abc"
        assert result.instructions is None
        gw_factory.get_gateway.assert_called_with(IntegratedPlatform.FLUTTERWAVE)

    async def test_stores_provider_ref(self):
        verification = _make_verification()
        payment = _make_payment()
        flw_gw = MagicMock()
        flw_gw.initialize_payment = AsyncMock(return_value="https://checkout.flutterwave.com/x")
        gw_factory = MagicMock()
        gw_factory.get_gateway = MagicMock(return_value=flw_gw)

        svc = _make_service(payment=payment, verification=verification, gateway_factory=gw_factory)
        await svc.initiate(_CUSTOMER_ID, InitiatePaymentDto(
            verification_id=_VERIFICATION_ID, method=PaymentMethod.CARD,
        ))

        update_calls = svc._payment_repo.update.call_args_list
        assert any(
            isinstance(call.args[1], UpdatePaymentDto) and call.args[1].provider_ref is not None
            for call in update_calls
        )

    async def test_rejects_wrong_owner(self):
        verification = _make_verification()
        verification.customer_id = "other-user"
        svc = _make_service(payment=_make_payment(), verification=verification)
        with pytest.raises(Exception):
            await svc.initiate(_CUSTOMER_ID, InitiatePaymentDto(
                verification_id=_VERIFICATION_ID, method=PaymentMethod.CARD,
            ))

    async def test_rejects_wrong_verification_status(self):
        verification = _make_verification(status=VerificationStatus.DRAFT.value)
        svc = _make_service(payment=_make_payment(), verification=verification)
        with pytest.raises(InvalidResourceStateException):
            await svc.initiate(_CUSTOMER_ID, InitiatePaymentDto(
                verification_id=_VERIFICATION_ID, method=PaymentMethod.CARD,
            ))


# ── BANK_TRANSFER initiation ───────────────────────────────────────


class TestInitiateBankTransfer:
    async def test_returns_virtual_account_instructions(self):
        from main.appodus_utils.integrations.payment.gateway.paystack.models import PaystackBankTransferResult
        verification = _make_verification()
        payment = _make_payment(method=PaymentMethod.BANK_TRANSFER.value, provider=PaymentProvider.PAYSTACK.value)

        ps_gw = MagicMock()
        ps_gw.charge_bank_transfer = AsyncMock(return_value=PaystackBankTransferResult(
            reference="ps_ref_001",
            bank="Wema Bank",
            account_number="9901234567",
            account_name="Veriprops/Ada Obi",
            expiry_date="2026-05-08T12:00:00",
        ))
        gw_factory = MagicMock()
        gw_factory.get_gateway = MagicMock(return_value=ps_gw)

        svc = _make_service(payment=payment, verification=verification, gateway_factory=gw_factory)
        result = await svc.initiate(_CUSTOMER_ID, InitiatePaymentDto(
            verification_id=_VERIFICATION_ID, method=PaymentMethod.BANK_TRANSFER,
        ))

        assert result.checkout_url is None
        assert result.instructions is not None
        assert result.instructions["virtualAccountBank"] == "Wema Bank"
        assert result.instructions["virtualAccountNumber"] == "9901234567"
        gw_factory.get_gateway.assert_called_with(IntegratedPlatform.PAYSTACK)

    async def test_stores_paystack_provider_ref(self):
        from main.appodus_utils.integrations.payment.gateway.paystack.models import PaystackBankTransferResult
        verification = _make_verification()
        payment = _make_payment(method=PaymentMethod.BANK_TRANSFER.value, provider=PaymentProvider.PAYSTACK.value)

        ps_gw = MagicMock()
        ps_gw.charge_bank_transfer = AsyncMock(return_value=PaystackBankTransferResult(
            reference="ps_ref_002", bank="GTBank", account_number="0123456789",
        ))
        gw_factory = MagicMock()
        gw_factory.get_gateway = MagicMock(return_value=ps_gw)

        svc = _make_service(payment=payment, verification=verification, gateway_factory=gw_factory)
        await svc.initiate(_CUSTOMER_ID, InitiatePaymentDto(
            verification_id=_VERIFICATION_ID, method=PaymentMethod.BANK_TRANSFER,
        ))

        update_calls = svc._payment_repo.update.call_args_list
        assert any(
            isinstance(c.args[1], UpdatePaymentDto) and c.args[1].provider_ref == "ps_ref_002"
            for c in update_calls
        )


# ── WIRE initiation ────────────────────────────────────────────────


class TestInitiateWire:
    async def test_returns_swift_and_beneficiary_from_settings(self):
        from main.app.config.settings import settings as app_settings
        verification = _make_verification()
        payment = _make_payment(method=PaymentMethod.WIRE.value, status=PaymentStatus.PENDING_WIRE.value)
        gw_factory = MagicMock()

        svc = _make_service(payment=payment, verification=verification, gateway_factory=gw_factory)
        result = await svc.initiate(_CUSTOMER_ID, InitiatePaymentDto(
            verification_id=_VERIFICATION_ID, method=PaymentMethod.WIRE,
        ))

        assert result.checkout_url is None
        instr = result.instructions
        assert instr["swift"] == app_settings.WIRE_SWIFT
        assert instr["beneficiaryBank"] == app_settings.WIRE_BENEFICIARY_BANK
        assert instr["beneficiary"] == app_settings.WIRE_BENEFICIARY
        assert "uploadProofTo" in instr

    async def test_reference_is_vid(self):
        verification = _make_verification(vid="VP-2026-123456")
        payment = _make_payment(method=PaymentMethod.WIRE.value, status=PaymentStatus.PENDING_WIRE.value)
        svc = _make_service(payment=payment, verification=verification)
        result = await svc.initiate(_CUSTOMER_ID, InitiatePaymentDto(
            verification_id=_VERIFICATION_ID, method=PaymentMethod.WIRE,
        ))
        assert result.instructions["reference"] == "VP-2026-123456"


# ── Webhook / record_provider_event ───────────────────────────────


class TestRecordProviderEvent:
    async def test_succeeded_transitions_verification_to_paid(self):
        payment = _make_payment(status=PaymentStatus.INITIATED.value, provider_ref="flw_ref_001")
        verification = _make_verification(status=VerificationStatus.PAYMENT_PENDING.value)
        svc = _make_service(payment=payment, verification=verification)

        await svc.record_provider_event(
            provider_ref="flw_ref_001",
            status=PaymentStatus.SUCCEEDED.value,
            payload={"reference": "flw_ref_001"},
        )

        svc._verification_service.transition.assert_called_once_with(
            str(_VERIFICATION_ID), VerificationStatus.PAID,
        )

    async def test_idempotent_duplicate_webhook(self):
        payment = _make_payment(
            status=PaymentStatus.SUCCEEDED.value,
            provider_ref="flw_ref_dup",
        )
        svc = _make_service(payment=payment, verification=_make_verification())

        await svc.record_provider_event(
            provider_ref="flw_ref_dup",
            status=PaymentStatus.SUCCEEDED.value,
            payload={},
        )

        svc._verification_service.transition.assert_not_called()

    async def test_unknown_provider_ref_is_silent(self):
        svc = _make_service(verification=_make_verification())
        svc._payment_repo.get_by_provider_ref = AsyncMock(return_value=None)

        await svc.record_provider_event(
            provider_ref="nonexistent",
            status=PaymentStatus.SUCCEEDED.value,
            payload={},
        )

        svc._verification_service.transition.assert_not_called()

    async def test_failed_payment_records_session_event(self):
        payment = _make_payment(status=PaymentStatus.INITIATED.value, provider_ref="flw_fail")
        svc = _make_service(payment=payment, verification=_make_verification())

        await svc.record_provider_event(
            provider_ref="flw_fail",
            status=PaymentStatus.FAILED.value,
            payload={},
        )

        svc._session_service.record_event.assert_called()


# ── Wire proof upload ──────────────────────────────────────────────


class TestUploadWireProof:
    async def test_sets_pending_wire_status(self):
        payment = _make_payment(method=PaymentMethod.WIRE.value, status=PaymentStatus.INITIATED.value)
        verification = _make_verification()
        refreshed = _make_payment(method=PaymentMethod.WIRE.value, status=PaymentStatus.PENDING_WIRE.value)
        svc = _make_service(payment=payment, verification=verification)
        svc._payment_repo.get_model = AsyncMock(side_effect=[payment, refreshed])

        result = await svc.upload_wire_proof(
            _CUSTOMER_ID, _PAYMENT_ID, WireProofDto(proof_url="https://s3.aws.com/proof.pdf"),
        )

        update_calls = svc._payment_repo.update.call_args_list
        assert any(
            isinstance(c.args[1], UpdatePaymentDto) and c.args[1].status == PaymentStatus.PENDING_WIRE
            for c in update_calls
        )

    async def test_rejects_wrong_owner(self):
        payment = _make_payment(method=PaymentMethod.WIRE.value)
        verification = _make_verification()
        verification.customer_id = "other-user"
        svc = _make_service(payment=payment, verification=verification)

        with pytest.raises(Exception):
            await svc.upload_wire_proof(
                _CUSTOMER_ID, _PAYMENT_ID, WireProofDto(proof_url="https://example.com/proof.pdf"),
            )


# ── Admin confirm_wire ─────────────────────────────────────────────


class TestConfirmWire:
    async def test_succeeded_and_transitions_verification(self):
        payment = _make_payment(method=PaymentMethod.WIRE.value, status=PaymentStatus.PENDING_WIRE.value)
        verification = _make_verification(status=VerificationStatus.PAYMENT_PENDING.value)
        refreshed = _make_payment(method=PaymentMethod.WIRE.value, status=PaymentStatus.SUCCEEDED.value)
        svc = _make_service(payment=payment, verification=verification)
        svc._payment_repo.get_model = AsyncMock(side_effect=[payment, refreshed])

        await svc.confirm_wire(_PAYMENT_ID, _ADMIN_ID, ConfirmWireDto())

        update_calls = svc._payment_repo.update.call_args_list
        assert any(
            isinstance(c.args[1], UpdatePaymentDto) and c.args[1].status == PaymentStatus.SUCCEEDED
            for c in update_calls
        )
        svc._verification_service.transition.assert_called_with(
            str(_VERIFICATION_ID), VerificationStatus.PAID,
        )

    async def test_rejects_already_succeeded(self):
        payment = _make_payment(method=PaymentMethod.WIRE.value, status=PaymentStatus.SUCCEEDED.value)
        svc = _make_service(payment=payment, verification=_make_verification())

        with pytest.raises(InvalidResourceStateException):
            await svc.confirm_wire(_PAYMENT_ID, _ADMIN_ID, ConfirmWireDto())

    async def test_payment_not_found(self):
        svc = _make_service(verification=_make_verification())
        svc._payment_repo.get_model = AsyncMock(return_value=None)

        with pytest.raises(ResourceNotFoundException):
            await svc.confirm_wire("nonexistent-id", _ADMIN_ID, ConfirmWireDto())
