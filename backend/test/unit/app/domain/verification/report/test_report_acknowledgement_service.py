"""ReportAcknowledgementService — the customer's acceptance of a report version's gate (§10.1).

The gate is per customer, case and report version: accepting it once opens that version, a
retried accept doesn't write a second record, and a new version asks again.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from main.app.domain.verification.report.acknowledgement.service import ReportAcknowledgementService
from test.utils.db_session import mock_db_session  # noqa: F401  (autouse fixture)


def _service(existing=None):
    svc = object.__new__(ReportAcknowledgementService)
    svc._acknowledgement_repo = MagicMock()
    svc._acknowledgement_repo.get_for = AsyncMock(return_value=existing)
    svc._acknowledgement_repo.create_return_model = AsyncMock(
        side_effect=lambda dto: SimpleNamespace(id="ack-1", **dto.model_dump()),
    )
    return svc


async def test_acknowledging_records_who_accepted_which_version_and_when():
    svc = _service()

    ack = await svc.acknowledge(customer_id="c1", verification_id="v1", report_id="r2", report_version=2)

    assert (ack.customer_id, ack.verification_id, ack.report_id, ack.report_version) == ("c1", "v1", "r2", 2)
    assert ack.acknowledged_at is not None


async def test_acknowledging_again_returns_the_first_record_instead_of_writing_another():
    first = SimpleNamespace(id="ack-0")
    svc = _service(existing=first)

    assert await svc.acknowledge(customer_id="c1", verification_id="v1", report_id="r2", report_version=2) is first
    svc._acknowledgement_repo.create_return_model.assert_not_awaited()


async def test_the_gate_is_checked_for_the_exact_customer_case_and_version():
    svc = _service(existing=SimpleNamespace(id="ack-0"))

    assert await svc.is_acknowledged("c1", "v1", 2) is True
    svc._acknowledgement_repo.get_for.assert_awaited_once_with("c1", "v1", 2)
    svc._acknowledgement_repo.get_for = AsyncMock(return_value=None)
    assert await svc.is_acknowledged("c1", "v1", 3) is False
