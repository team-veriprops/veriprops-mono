"""Unit tests for RecheckService (S44)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from main.app.domain.verification.models import VerificationStatus
from main.app.domain.verification.recheck.models import (
    RecheckStatus,
    SubmitRecheckDto,
)
from main.app.domain.verification.recheck.service import RecheckService
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


def _mock_verification(status=VerificationStatus.COMPLETED.value, customer_id="cust-1", tier="STANDARD"):
    v = MagicMock()
    v.id = "ver-1"
    v.status = status
    v.customer_id = customer_id
    v.tier = tier
    return v


def _mock_recheck(request_id="req-1", status=RecheckStatus.PENDING.value, scope_roles='["SURVEYOR"]', verification_id="ver-1"):
    r = MagicMock()
    r.id = request_id
    r.verification_id = verification_id
    r.reason = "Something looks off"
    r.scope_roles = scope_roles
    r.status = status
    r.requested_by = "cust-1"
    r.reviewed_by = None
    r.reviewed_at = None
    r.rejection_reason = None
    r.price = None
    r.date_created = str(datetime.now(timezone.utc))
    return r


def _make_svc(recheck=None, ver=None):
    repo = MagicMock()
    repo.create = AsyncMock(return_value=recheck or _mock_recheck())
    repo.get_model = AsyncMock(return_value=recheck or _mock_recheck())
    repo.update = AsyncMock()
    repo.get_all = AsyncMock(return_value=[])

    ver_repo = MagicMock()
    ver_repo.get_model = AsyncMock(return_value=ver or _mock_verification())

    svc = RecheckService(repo=repo, ver_repo=ver_repo)
    return svc, repo, ver_repo


class TestSubmit:
    async def test_raises_if_verification_not_found(self):
        svc, _, ver_repo = _make_svc()
        ver_repo.get_model = AsyncMock(return_value=None)

        with pytest.raises(ResourceNotFoundException):
            await svc.submit(
                "ver-1", "cust-1",
                SubmitRecheckDto(reason="Something wrong", scope_roles=["SURVEYOR"]),
            )

    async def test_raises_if_not_completed(self):
        ver = _mock_verification(status=VerificationStatus.IN_PROGRESS.value)
        svc, _, _ = _make_svc(ver=ver)

        with pytest.raises(ValidationException, match="COMPLETED"):
            await svc.submit(
                "ver-1", "cust-1",
                SubmitRecheckDto(reason="Something wrong", scope_roles=["SURVEYOR"]),
            )

    async def test_creates_recheck_request(self):
        svc, repo, _ = _make_svc()

        await svc.submit(
            "ver-1", "cust-1",
            SubmitRecheckDto(reason="Something wrong", scope_roles=["SURVEYOR", "LAWYER"]),
        )

        repo.create.assert_called_once()
        call_dto = repo.create.call_args[0][0]
        assert call_dto.status == RecheckStatus.PENDING.value


class TestApprove:
    async def test_approve_transitions_verification_to_in_progress(self):
        recheck = _mock_recheck(status=RecheckStatus.PENDING.value, scope_roles='["SURVEYOR"]')
        svc, repo, _ = _make_svc(recheck=recheck)

        with patch("main.app.domain.verification.recheck.service.di") as mock_di:
            ver_svc = MagicMock()
            ver_svc.transition = AsyncMock()
            task_svc = MagicMock()
            task_svc._tasks = MagicMock()
            task_svc._tasks.create_return_model = AsyncMock()
            notif_svc = MagicMock()
            notif_svc.emit = AsyncMock()

            def _get_item(cls):
                if "VerificationService" in str(cls):
                    return ver_svc
                if "TaskService" in str(cls):
                    return task_svc
                return notif_svc

            mock_di.__getitem__ = MagicMock(side_effect=_get_item)

            await svc.approve("req-1", "admin-1")

        ver_svc.transition.assert_called_once_with(
            "ver-1", VerificationStatus.IN_PROGRESS, actor_id="admin-1"
        )

    async def test_approve_updates_status_to_approved(self):
        recheck = _mock_recheck(status=RecheckStatus.PENDING.value, scope_roles='["SURVEYOR"]')
        svc, repo, _ = _make_svc(recheck=recheck)

        with patch("main.app.domain.verification.recheck.service.di") as mock_di:
            mock_di.__getitem__ = MagicMock(return_value=MagicMock(
                transition=AsyncMock(),
                _tasks=MagicMock(create_return_model=AsyncMock()),
                emit=AsyncMock(),
            ))
            await svc.approve("req-1", "admin-1")

        repo.update.assert_called_once()
        call_dto = repo.update.call_args[0][1]
        assert call_dto.status == RecheckStatus.APPROVED.value
