"""PayoutDisbursementService — approved payouts leave as bank transfers, in batches (§15.1).

The one property everything here protects: **an agent is never paid twice.**

* A payout is claimed APPROVED → PROCESSING, under a fresh transfer reference, and that
  claim commits *before* the gateway is called. A crash after the money moved can only
  leave it PROCESSING, never back in the queue.
* The reference is stable per attempt, and both gateways refuse a second transfer under
  a reference they have seen.
* Only the gateway's own "no" (a decline, then no transfer under our reference) fails a
  payout. An unreachable gateway or a lost answer leaves it PROCESSING for the next
  reconcile, which asks the gateway by reference.
* A webhook only says "go and look": the payout settles from what the gateway reports
  when asked, and only for the attempt the webhook names.

A failed transfer keeps its funds reserved; finance retries or rejects it.
"""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.core.events import EventType
from main.app.domain.audit.models import AuditActionType
from main.app.domain.payout import disbursement as disbursement_module
from main.app.domain.payout.disbursement import PayoutDisbursementService, transfer_reference_for
from main.app.domain.payout.models import PayoutStatus
from main.appodus_utils import Utils
from main.appodus_utils.db.session import get_db_session_or_none
from main.appodus_utils.integrations.exception.exceptions import IntegrationException, IntegrationFatalException
from main.appodus_utils.integrations.payment.gateway.http import GatewayDeclined
from main.appodus_utils.integrations.payment.gateway.models import GatewayTransfer, GatewayTransferStatus
from test.utils.repo_fakes import fake_claim_transition

PAYOUT_ID = "0123456789abcdef0123456789abcdef"


@pytest.fixture(autouse=True)
def _independent(independent_sessions):
    return independent_sessions


@pytest.fixture(autouse=True)
def events(monkeypatch):
    published = []

    async def _pub(event):
        published.append(event)

    monkeypatch.setattr(disbursement_module, "publish_domain_event", _pub)
    return published


def _payout(pid=PAYOUT_ID, status=PayoutStatus.APPROVED, attempts=0, reference=None, sent_at=None, **over):
    row = SimpleNamespace(
        id=pid, agent_id="a-1", amount_minor=50_000, adjustment_minor=0, fee_minor=1_000, currency="NGN",
        status=status.value, bank_code="058", bank_name="Guaranty Trust Bank", provider="paystack",
        account_number="0123456789", account_name="TEST ACCOUNT 6789", transfer_reference=reference,
        transfer_attempts=attempts, gateway_transfer_id=None, failure_reason=None, sent_at=sent_at,
        settled_at=None, deleted=False,
    )
    for key, value in over.items():
        setattr(row, key, value)
    return row


def _transfer(reference, status=GatewayTransferStatus.SUCCEEDED, reason=None):
    return GatewayTransfer(
        reference=reference, gateway_transfer_id="TRF_1", status=status, amount_minor=49_000, failure_reason=reason,
    )


def _service(*rows, gateway=None):
    table = {r.id: r for r in rows}
    svc = object.__new__(PayoutDisbursementService)
    svc._payout_repo = AsyncMock()
    svc._payout_repo.get_model = AsyncMock(side_effect=lambda pid: table.get(pid))
    svc._payout_repo.claim_transition = fake_claim_transition(table)

    async def _ids(status, limit, sent_before=None):
        return [
            r.id for r in table.values()
            if r.status == status.value and (sent_before is None or (r.sent_at and r.sent_at <= sent_before))
        ][:limit]

    svc._payout_repo.ids_in_status = AsyncMock(side_effect=_ids)
    svc._payout_repo.count_in_status = AsyncMock(
        side_effect=lambda status: sum(1 for r in table.values() if r.status == status.value),
    )
    svc._payout_repo.get_by_transfer_reference = AsyncMock(
        side_effect=lambda ref: next((r for r in table.values() if r.transfer_reference == ref), None),
    )
    svc._gateway = gateway or AsyncMock()
    if gateway is None:
        svc._gateway.send_transfer = AsyncMock(side_effect=lambda req: _transfer(req.reference))
        svc._gateway.get_transfer = AsyncMock(return_value=None)
    svc._gateways = MagicMock()
    svc._gateways.transfers = MagicMock(return_value=svc._gateway)
    svc._audit = MagicMock()
    return svc


def _audited(svc):
    return [c.kwargs["action"] for c in svc._audit.schedule.call_args_list]


class TestReference:
    def test_each_attempt_has_its_own_reference_both_gateways_accept(self):
        first, second = transfer_reference_for(PAYOUT_ID, 1), transfer_reference_for(PAYOUT_ID, 2)
        assert first == f"vp-po-{PAYOUT_ID}-1"
        assert first != second


class TestDisburse:
    async def test_an_approved_payout_is_sent_net_of_its_fee_and_paid(self, events):
        row = _payout()
        svc = _service(row)

        outcome = await svc.run()

        request = svc._gateway.send_transfer.call_args.args[0]
        assert (request.amount_minor, request.bank_code, request.account_number, request.account_name) == (
            49_000, "058", "0123456789", "TEST ACCOUNT 6789",
        )
        assert request.reference == transfer_reference_for(PAYOUT_ID, 1)
        assert row.status == PayoutStatus.PAID.value
        assert (row.transfer_attempts, row.gateway_transfer_id) == (1, "TRF_1")
        assert row.settled_at is not None
        assert [e.type for e in events] == [EventType.PAYOUT_PAID]
        assert (outcome.paid, outcome.failed, outcome.in_flight, outcome.remaining) == (1, 0, 0, 0)

    async def test_the_claim_commits_before_the_gateway_is_called(self):
        row = _payout()
        svc = _service(row)
        seen = {}

        async def _send(req):
            seen["status"] = row.status
            seen["open_session"] = get_db_session_or_none()
            return _transfer(req.reference)

        svc._gateway.send_transfer = AsyncMock(side_effect=_send)

        await svc.run()

        # Already PROCESSING when the money moves, and no transaction is open around the call
        # that could still roll that claim back.
        assert seen == {"status": PayoutStatus.PROCESSING.value, "open_session": None}

    async def test_the_payout_goes_through_its_accounts_own_gateway(self):
        svc = _service(_payout(provider="flutterwave"))

        await svc.run()

        from main.app.config.settings import IntegratedPlatform
        svc._gateways.transfers.assert_called_with(IntegratedPlatform.FLUTTERWAVE)

    async def test_a_queued_transfer_stays_processing_until_the_gateway_settles_it(self, events):
        row = _payout()
        svc = _service(row)
        svc._gateway.send_transfer = AsyncMock(
            side_effect=lambda req: _transfer(req.reference, GatewayTransferStatus.PENDING),
        )

        outcome = await svc.run()

        assert row.status == PayoutStatus.PROCESSING.value
        assert row.gateway_transfer_id == "TRF_1"
        assert events == []
        assert outcome.in_flight == 1

    async def test_a_decline_with_no_transfer_under_our_reference_fails_the_payout(self, events):
        row = _payout()
        svc = _service(row)
        svc._gateway.send_transfer = AsyncMock(side_effect=GatewayDeclined("declined"))

        outcome = await svc.run()

        assert row.status == PayoutStatus.FAILED.value
        assert row.failure_reason
        assert AuditActionType.PAYOUT_TRANSFER_FAILED in _audited(svc)
        assert events == []  # finance decides; the funds stay reserved
        assert outcome.failed == 1

    async def test_a_decline_for_a_reference_already_used_follows_the_existing_transfer(self):
        # Flutterwave: "Payout with this ref already exists" — the first send did land.
        row = _payout()
        svc = _service(row)
        svc._gateway.send_transfer = AsyncMock(side_effect=GatewayDeclined("duplicate"))
        svc._gateway.get_transfer = AsyncMock(side_effect=lambda ref: _transfer(ref))

        await svc.run()

        assert row.status == PayoutStatus.PAID.value

    async def test_an_unreachable_gateway_leaves_the_payout_processing(self):
        row = _payout()
        svc = _service(row)
        svc._gateway.send_transfer = AsyncMock(side_effect=IntegrationException("unreachable"))
        svc._gateway.get_transfer = AsyncMock(side_effect=IntegrationException("unreachable"))

        outcome = await svc.run()

        # The transfer may have landed: failing it would let finance pay it a second time.
        assert row.status == PayoutStatus.PROCESSING.value
        assert outcome.in_flight == 1

    async def test_a_lost_answer_is_recovered_by_asking_for_our_reference(self):
        row = _payout()
        svc = _service(row)
        svc._gateway.send_transfer = AsyncMock(side_effect=IntegrationException("timed out"))
        svc._gateway.get_transfer = AsyncMock(side_effect=lambda ref: _transfer(ref))

        await svc.run()

        assert row.status == PayoutStatus.PAID.value

    async def test_a_decline_whose_lookup_cannot_be_made_stays_processing(self):
        row = _payout()
        svc = _service(row)
        svc._gateway.send_transfer = AsyncMock(side_effect=GatewayDeclined("declined"))
        svc._gateway.get_transfer = AsyncMock(side_effect=IntegrationException("unreachable"))

        await svc.run()

        assert row.status == PayoutStatus.PROCESSING.value

    async def test_an_account_no_gateway_resolved_fails_without_a_transfer(self):
        row = _payout(provider=None)
        svc = _service(row)
        svc._gateways.transfers = MagicMock(side_effect=IntegrationFatalException("re-add"))

        await svc.run()

        assert row.status == PayoutStatus.FAILED.value
        svc._gateway.send_transfer.assert_not_called()

    async def test_a_payout_finance_pulled_back_meanwhile_is_not_sent(self):
        row = _payout()
        svc = _service(row)
        # Listed as APPROVED, then held before its turn in the batch.
        original = svc._payout_repo.ids_in_status.side_effect

        async def _ids_then_hold(status, limit, sent_before=None):
            ids = await original(status, limit, sent_before)
            row.status = PayoutStatus.HELD.value
            return ids

        svc._payout_repo.ids_in_status = AsyncMock(side_effect=_ids_then_hold)

        await svc.run()

        svc._gateway.send_transfer.assert_not_called()
        assert row.status == PayoutStatus.HELD.value

    async def test_a_payout_that_cannot_be_paid_fails_without_stopping_the_batch(self):
        # Adjusted below its fee, and a payout from before accounts carried a bank code.
        swallowed = _payout(pid=f"{1:032x}", adjustment_minor=-49_000)
        legacy = _payout(pid=f"{2:032x}", bank_code=None)
        fine = _payout(pid=f"{3:032x}")
        svc = _service(swallowed, legacy, fine)

        outcome = await svc.run()

        assert (swallowed.status, legacy.status, fine.status) == (
            PayoutStatus.FAILED.value, PayoutStatus.FAILED.value, PayoutStatus.PAID.value,
        )
        assert svc._gateway.send_transfer.await_count == 1
        assert (outcome.paid, outcome.failed) == (1, 2)

    async def test_an_unreadable_gateway_answer_leaves_the_payout_in_flight_and_the_batch_going(self):
        first, second = _payout(pid=f"{1:032x}"), _payout(pid=f"{2:032x}")
        svc = _service(first, second)
        answers = [KeyError("data"), None]

        async def _send(req):
            answer = answers.pop(0)
            if answer is not None:
                raise answer
            return _transfer(req.reference)

        svc._gateway.send_transfer = AsyncMock(side_effect=_send)

        outcome = await svc.run()

        assert (first.status, second.status) == (PayoutStatus.PROCESSING.value, PayoutStatus.PAID.value)
        assert (outcome.in_flight, outcome.paid) == (1, 1)

    async def test_the_gateways_own_reason_for_a_decline_reaches_finance(self):
        row = _payout()
        svc = _service(row)
        svc._gateway.send_transfer = AsyncMock(
            side_effect=GatewayDeclined("declined", provider_message="Your balance is not enough to fulfil this request"),
        )

        await svc.run()

        assert "balance is not enough" in row.failure_reason

    async def test_the_person_who_pressed_disburse_is_on_the_audit(self):
        svc = _service(_payout())

        await svc.run(actor_id="fin-7")

        sent = [c.kwargs for c in svc._audit.schedule.call_args_list
                if c.kwargs["action"] == AuditActionType.PAYOUT_TRANSFER_SENT]
        assert sent and sent[0]["actor_id"] == "fin-7"

    async def test_two_overlapping_batches_send_a_payout_once(self):
        # The sweep and the button both listed it; only one claim can take it to PROCESSING.
        from main.app.domain.payout.models import DisbursementOutcomeDto

        row = _payout()
        svc = _service(row)

        await svc._disburse(row.id, DisbursementOutcomeDto())
        await svc._disburse(row.id, DisbursementOutcomeDto())

        assert svc._gateway.send_transfer.await_count == 1
        assert row.transfer_attempts == 1

    async def test_a_batch_takes_a_bounded_number_and_reports_what_is_left(self):
        rows = [_payout(pid=f"{i:032x}") for i in range(3)]
        svc = _service(*rows)

        outcome = await svc.run(limit=2)

        assert (outcome.paid, outcome.remaining) == (2, 1)

    async def test_a_retry_is_sent_under_a_new_reference(self):
        row = _payout(attempts=1, reference=transfer_reference_for(PAYOUT_ID, 1))
        svc = _service(row)

        await svc.run()

        assert svc._gateway.send_transfer.call_args.args[0].reference == transfer_reference_for(PAYOUT_ID, 2)
        assert row.transfer_attempts == 2


class TestReconcile:
    async def test_a_transfer_left_processing_is_settled_by_asking_the_gateway(self, events):
        ref = transfer_reference_for(PAYOUT_ID, 1)
        row = _payout(status=PayoutStatus.PROCESSING, attempts=1, reference=ref,
                      sent_at=Utils.datetime_now() - timedelta(hours=2))
        svc = _service(row)
        svc._gateway.get_transfer = AsyncMock(side_effect=lambda r: _transfer(r))

        outcome = await svc.run()

        svc._gateway.get_transfer.assert_awaited_with(ref)
        assert row.status == PayoutStatus.PAID.value
        assert outcome.paid == 1
        svc._gateway.send_transfer.assert_not_called()

    async def test_a_transfer_the_gateway_never_took_fails_once_the_grace_has_passed(self):
        row = _payout(status=PayoutStatus.PROCESSING, attempts=1, reference=transfer_reference_for(PAYOUT_ID, 1),
                      sent_at=Utils.datetime_now() - timedelta(hours=2))
        svc = _service(row)

        await svc.run()

        assert row.status == PayoutStatus.FAILED.value

    async def test_a_transfer_sent_moments_ago_is_left_to_its_webhook(self):
        row = _payout(status=PayoutStatus.PROCESSING, attempts=1, reference=transfer_reference_for(PAYOUT_ID, 1),
                      sent_at=Utils.datetime_now())
        svc = _service(row)

        await svc.run()

        svc._gateway.get_transfer.assert_not_called()
        assert row.status == PayoutStatus.PROCESSING.value


class TestWebhookSettlement:
    async def test_a_webhook_settles_from_what_the_gateway_reports(self, events):
        ref = transfer_reference_for(PAYOUT_ID, 1)
        row = _payout(status=PayoutStatus.PROCESSING, attempts=1, reference=ref)
        svc = _service(row)
        svc._gateway.get_transfer = AsyncMock(side_effect=lambda r: _transfer(r))

        await svc.settle_from_gateway(ref)

        assert row.status == PayoutStatus.PAID.value
        assert [e.type for e in events] == [EventType.PAYOUT_PAID]

    async def test_a_repeated_webhook_pays_nothing_twice(self, events):
        ref = transfer_reference_for(PAYOUT_ID, 1)
        row = _payout(status=PayoutStatus.PROCESSING, attempts=1, reference=ref)
        svc = _service(row)
        svc._gateway.get_transfer = AsyncMock(side_effect=lambda r: _transfer(r))

        await svc.settle_from_gateway(ref)
        await svc.settle_from_gateway(ref)

        assert len(events) == 1
        assert _audited(svc).count(AuditActionType.PAYOUT_PAID) == 1

    async def test_a_reversal_after_payment_fails_the_payout_for_finance(self):
        ref = transfer_reference_for(PAYOUT_ID, 1)
        row = _payout(status=PayoutStatus.PAID, attempts=1, reference=ref)
        svc = _service(row)
        svc._gateway.get_transfer = AsyncMock(
            side_effect=lambda r: _transfer(r, GatewayTransferStatus.FAILED, "reversed by the bank"),
        )

        await svc.settle_from_gateway(ref)

        assert row.status == PayoutStatus.FAILED.value
        assert row.failure_reason == "reversed by the bank"

    async def test_news_of_an_earlier_attempt_cannot_touch_the_current_one(self):
        # Attempt 1 failed and finance retried; attempt 2 is in flight.
        row = _payout(status=PayoutStatus.PROCESSING, attempts=2, reference=transfer_reference_for(PAYOUT_ID, 2))
        svc = _service(row)
        svc._gateway.get_transfer = AsyncMock(
            side_effect=lambda r: _transfer(r, GatewayTransferStatus.FAILED, "old attempt"),
        )

        await svc.settle_from_gateway(transfer_reference_for(PAYOUT_ID, 1))

        assert row.status == PayoutStatus.PROCESSING.value

    async def test_a_late_success_for_the_current_attempt_turns_a_failure_into_payment(self, events):
        # Reconcile found nothing in time and failed it; then the transfer's success arrives.
        ref = transfer_reference_for(PAYOUT_ID, 1)
        row = _payout(status=PayoutStatus.FAILED, attempts=1, reference=ref, failure_reason="no record")
        svc = _service(row)
        svc._gateway.get_transfer = AsyncMock(side_effect=lambda r: _transfer(r))

        await svc.settle_from_gateway(ref)

        assert row.status == PayoutStatus.PAID.value
        assert row.failure_reason is None
        assert [e.type for e in events] == [EventType.PAYOUT_PAID]

    async def test_a_reference_that_is_not_a_payout_is_ignored(self):
        svc = _service()

        await svc.settle_from_gateway("vp-po-ffffffffffffffffffffffffffffffff-1")

        svc._gateway.get_transfer.assert_not_called()
