"""Unit tests for DisputeService and DisputeValidator (S46)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from main.app.domain.verification.dispute.models import (
    DisputeOutcome,
    DisputeStatus,
    ResolveDisputeDto,
    SubmitDisputeDto,
)
from main.app.domain.verification.dispute.service import DisputeService
from main.app.domain.verification.dispute.validator import DisputeValidator
from main.app.domain.verification.models import VerificationStatus
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import (
    ResourceNotFoundException,
    ValidationException,
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


def _mock_verification(status=VerificationStatus.COMPLETED.value, vid="VID-001", customer_id="cust-1"):
    v = MagicMock()
    v.id = "ver-1"
    v.vid = vid
    v.status = status
    v.customer_id = customer_id
    return v


def _mock_dispute(dispute_id="d-1", verification_id="ver-1", status=DisputeStatus.PENDING.value):
    d = MagicMock()
    d.id = dispute_id
    d.verification_id = verification_id
    d.dispute_type = "INACCURATE_FINDINGS"
    d.description = "x" * 120
    d.status = status
    d.submitted_by = "cust-1"
    d.submitted_at = str(datetime.now(timezone.utc))
    d.date_created = str(datetime.now(timezone.utc))
    return d


def _make_svc(dispute=None, ver=None):
    repo = MagicMock()
    repo.create = AsyncMock(return_value=dispute or _mock_dispute())
    repo.get_model = AsyncMock(return_value=dispute or _mock_dispute())
    repo.update = AsyncMock()
    repo.get_all = AsyncMock(return_value=[])

    resolution_repo = MagicMock()
    resolution_repo.create = AsyncMock(return_value=MagicMock(
        id="res-1", dispute_id="d-1", outcome=DisputeOutcome.REJECTED.value,
        resolution_note="test", resolved_by="admin-1",
        resolved_at=str(datetime.now(timezone.utc)),
    ))

    ver_repo = MagicMock()
    ver_repo.get_model = AsyncMock(return_value=ver or _mock_verification())

    validator = DisputeValidator()

    svc = DisputeService(
        repo=repo, resolution_repo=resolution_repo,
        ver_repo=ver_repo, validator=validator,
    )
    return svc, repo, resolution_repo, ver_repo


# ── Validator unit tests ──────────────────────────────────────────────────────


class TestDisputeValidator:
    def test_description_too_short_raises(self):
        v = DisputeValidator()
        with pytest.raises(ValidationException, match="at least 100 characters"):
            v.assert_description_length("too short")

    def test_description_exactly_100_passes(self):
        v = DisputeValidator()
        v.assert_description_length("a" * 100)  # must not raise

    def test_non_completed_status_raises(self):
        v = DisputeValidator()
        with pytest.raises(ValidationException, match="COMPLETED"):
            v.assert_can_dispute(VerificationStatus.IN_PROGRESS.value)

    def test_completed_status_passes(self):
        v = DisputeValidator()
        v.assert_can_dispute(VerificationStatus.COMPLETED.value)  # must not raise


# ── Service tests ─────────────────────────────────────────────────────────────


class TestSubmit:
    async def test_submit_raises_if_verification_not_found(self):
        svc, _, _, ver_repo = _make_svc()
        ver_repo.get_model = AsyncMock(return_value=None)

        with pytest.raises(ResourceNotFoundException):
            await svc.submit(
                "ver-1", "cust-1",
                SubmitDisputeDto(
                    dispute_type="INACCURATE_FINDINGS",
                    description="a" * 120,
                ),
            )

    async def test_submit_raises_on_short_description(self):
        svc, _, _, _ = _make_svc()

        with pytest.raises(ValidationException, match="at least 100 characters"):
            await svc.submit(
                "ver-1", "cust-1",
                SubmitDisputeDto(dispute_type="INACCURATE_FINDINGS", description="short"),
            )

    async def test_submit_raises_if_not_completed(self):
        ver = _mock_verification(status=VerificationStatus.IN_PROGRESS.value)
        svc, _, _, _ = _make_svc(ver=ver)

        with pytest.raises(ValidationException, match="COMPLETED"):
            await svc.submit(
                "ver-1", "cust-1",
                SubmitDisputeDto(
                    dispute_type="INACCURATE_FINDINGS",
                    description="a" * 120,
                ),
            )

    async def test_submit_creates_dispute_row(self):
        svc, repo, _, _ = _make_svc()

        with patch("main.app.domain.verification.dispute.service.di") as mock_di:
            ver_svc = MagicMock()
            ver_svc.transition = AsyncMock()
            notif_svc = MagicMock()
            notif_svc.emit = AsyncMock()
            mock_di.__getitem__ = MagicMock(side_effect=lambda cls: ver_svc if "VerificationService" in str(cls) else notif_svc)

            await svc.submit(
                "ver-1", "cust-1",
                SubmitDisputeDto(
                    dispute_type="INACCURATE_FINDINGS",
                    description="a" * 120,
                ),
            )

        repo.create.assert_called_once()


class TestResolve:
    async def test_rejected_outcome_transitions_to_completed(self):
        svc, _, resolution_repo, ver_repo = _make_svc()

        with patch("main.app.domain.verification.dispute.service.di") as mock_di:
            ver_svc = MagicMock()
            ver_svc.transition = AsyncMock()
            thread_svc = MagicMock()
            thread_svc.post_system_message_for_verification = AsyncMock()
            notif_svc = MagicMock()
            notif_svc.emit = AsyncMock()

            def _get_item(cls):
                if "VerificationService" in str(cls):
                    return ver_svc
                if "ThreadService" in str(cls):
                    return thread_svc
                return notif_svc

            mock_di.__getitem__ = MagicMock(side_effect=_get_item)

            await svc.resolve(
                "d-1", "admin-1",
                ResolveDisputeDto(outcome=DisputeOutcome.REJECTED, resolution_note="Claim invalid"),
            )

        ver_svc.transition.assert_called_once()
        call_args = ver_svc.transition.call_args
        assert call_args[0][1] == VerificationStatus.COMPLETED
