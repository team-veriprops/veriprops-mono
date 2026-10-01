"""CustomerReportService (§10): owner-gated report view, only-when-released, access-gate
acknowledgement recorded against the version, and PDF render via the facade."""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.core.state.status import AgentRole, VerificationTier
from main.app.domain.verification.report.customer_service import CustomerReportService
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import ResourceNotFoundException


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


def _verification(tier=VerificationTier.STANDARD):
    return SimpleNamespace(id="v-1", vid="VP-1", tier=tier.value, property_id="p-1")


def _report():
    return SimpleNamespace(
        id="rep-1", verification_id="v-1", report_version=2, composite_trust_score=88,
        released_at=None, findings={"REGISTRY": {"ok": True}, "FIELD": {"ok": True},
                                    "SURVEYOR": {"ok": True}},
    )


def _service(*, released=True, acknowledged=False):
    svc = object.__new__(CustomerReportService)
    svc._verifications = MagicMock()
    svc._reports = MagicMock()
    svc._acks = MagicMock()
    svc._properties = MagicMock()
    svc._pdf_factory = MagicMock()
    svc._config = MagicMock(get_int=AsyncMock(return_value=120))

    svc._verifications.get_owned = AsyncMock(return_value=_verification())
    svc._reports.get_released = AsyncMock(return_value=_report() if released else None)
    svc._acks.is_acknowledged = AsyncMock(return_value=acknowledged)
    svc._acks.acknowledge = AsyncMock()
    svc._properties.get_model = AsyncMock(return_value=SimpleNamespace(address="12 Lekki"))
    provider = MagicMock()
    provider.render = MagicMock(return_value=b"%PDF-1.4 stub")
    svc._pdf_factory.get_active_provider = MagicMock(return_value=provider)
    return svc


class TestGetReport:
    async def test_returns_content_for_released_report(self):
        svc = _service(acknowledged=True)
        c = await svc.get_report("v-1", "cust-1")
        assert c.vid == "VP-1"
        assert c.trust_band == "Caution"  # 88 → Caution
        assert c.acknowledged is True
        assert any(s.title == "Registry & Title" for s in c.sections)

    async def test_raises_when_no_released_report(self):
        svc = _service(released=False)
        with pytest.raises(ResourceNotFoundException):
            await svc.get_report("v-1", "cust-1")

    async def test_ownership_gate_is_invoked(self):
        svc = _service()
        await svc.get_report("v-1", "cust-1")
        svc._verifications.get_owned.assert_awaited_once_with("v-1", "cust-1")


class TestAcknowledge:
    async def test_records_ack_against_version(self):
        svc = _service(acknowledged=False)
        c = await svc.acknowledge("v-1", "cust-1")
        svc._acks.acknowledge.assert_awaited_once()
        kwargs = svc._acks.acknowledge.await_args.kwargs
        assert kwargs["report_version"] == 2
        assert kwargs["customer_id"] == "cust-1"
        assert c.acknowledged is True


class TestActions:
    """What the owner may do next is the backend's call (§19.2, §19.3), so the page renders it."""

    async def test_lists_the_tiers_above_the_case_and_the_parts_a_dispute_can_name(self):
        content = await _service().get_report("v-1", "c-1")

        assert content.actions.upgrade_tiers == [VerificationTier.PREMIUM]
        assert content.actions.dispute_roles == [AgentRole.REGISTRY, AgentRole.FIELD, AgentRole.SURVEYOR]
        assert content.actions.dispute_min_description_chars == 120

    async def test_a_premium_case_has_nothing_to_upgrade_to(self):
        svc = _service()
        svc._verifications.get_owned = AsyncMock(return_value=_verification(VerificationTier.PREMIUM))

        content = await svc.get_report("v-1", "c-1")

        assert content.actions.upgrade_tiers == []
        assert AgentRole.LAWYER in content.actions.dispute_roles

    async def test_a_shared_copy_carries_no_owner_actions(self):
        svc = _service()
        svc._verifications.get_by_id = AsyncMock(return_value=_verification())

        assert (await svc.build_shared_content("v-1")).actions is None


class TestPdf:
    async def test_renders_pdf_bytes(self):
        svc = _service()
        out = await svc.render_pdf("v-1", "cust-1")
        assert out[:4] == b"%PDF"
