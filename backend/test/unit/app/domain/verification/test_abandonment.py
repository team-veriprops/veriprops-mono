"""Unit tests for abandonment recovery detection and email dispatch (S52)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from main.app.domain.verification.models import UpdateVerificationDto, VerificationStatus
from main.app.domain.verification.service import VerificationService
from main.appodus_utils.db.session import db_session_ctx


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


def _mock_verification(
    ver_id="ver-1",
    customer_id="cust-1",
    vid="VP-2026-AAAA",
    status=VerificationStatus.DRAFT.value,
    abandonment_email_sent_at=None,
    draft_step=1,
):
    v = MagicMock()
    v.id = ver_id
    v.customer_id = customer_id
    v.vid = vid
    v.status = status
    v.abandonment_email_sent_at = abandonment_email_sent_at
    v.draft_step = draft_step
    v.date_created = datetime(2026, 5, 1, tzinfo=timezone.utc)
    v.date_updated = datetime(2026, 5, 1, tzinfo=timezone.utc)
    return v


def _mock_user(user_id="cust-1"):
    u = MagicMock()
    u.id = user_id
    return u


def _make_svc(abandoned_verifications=None):
    """Build a minimal VerificationService with mocked repo."""
    repo = MagicMock()
    repo.list_abandoned = AsyncMock(return_value=abandoned_verifications or [])
    repo.update = AsyncMock()

    property_repo = MagicMock()
    validator = MagicMock()
    pricing = MagicMock()
    consent = MagicMock()
    audit = MagicMock()
    audit.schedule = MagicMock()
    storage = MagicMock()

    svc = VerificationService.__new__(VerificationService)
    svc._repo = repo
    svc._property_repo = property_repo
    svc._validator = validator
    svc._pricing = pricing
    svc._consent_service = consent
    svc._audit = audit
    svc._storage_factory = storage
    return svc, repo


class TestGetAbandonments:
    async def test_delegates_to_repo(self):
        abandoned = [_mock_verification()]
        svc, repo = _make_svc(abandoned_verifications=abandoned)

        result = await svc.get_abandonments()

        repo.list_abandoned.assert_awaited_once_with(older_than_hours=24)
        assert result == abandoned

    async def test_returns_empty_when_none(self):
        svc, _ = _make_svc(abandoned_verifications=[])
        result = await svc.get_abandonments()
        assert result == []


class TestSendAbandonmentEmails:
    async def test_sends_email_and_marks_sent(self):
        ver = _mock_verification()
        user = _mock_user()
        svc, repo = _make_svc(abandoned_verifications=[ver])

        mock_msg_svc = MagicMock()
        mock_msg_svc.send_abandonment_recovery = AsyncMock()
        mock_user_repo = MagicMock()
        mock_user_repo.get_model = AsyncMock(return_value=user)

        with (
            patch("main.app.domain.verification.service.di") as mock_di,
        ):
            from main.app.domain.message.verification_messages import VerificationMessages
            from main.app.domain.user.repo import UserRepo
            mock_di.__getitem__ = MagicMock(side_effect=lambda cls: (
                mock_msg_svc if cls == VerificationMessages else mock_user_repo
            ))

            count = await svc.send_abandonment_emails()

        assert count == 1
        repo.update.assert_awaited_once()
        # Verify abandonment_email_sent_at was set
        _, dto = repo.update.call_args[0]
        assert isinstance(dto, UpdateVerificationDto)
        assert dto.abandonment_email_sent_at is not None

    async def test_skips_when_user_not_found(self):
        ver = _mock_verification()
        svc, repo = _make_svc(abandoned_verifications=[ver])

        mock_msg_svc = MagicMock()
        mock_msg_svc.send_abandonment_recovery = AsyncMock()
        mock_user_repo = MagicMock()
        mock_user_repo.get_model = AsyncMock(return_value=None)  # user missing

        with patch("main.app.domain.verification.service.di") as mock_di:
            from main.app.domain.message.verification_messages import VerificationMessages
            from main.app.domain.user.repo import UserRepo
            mock_di.__getitem__ = MagicMock(side_effect=lambda cls: (
                mock_msg_svc if cls == VerificationMessages else mock_user_repo
            ))

            count = await svc.send_abandonment_emails()

        assert count == 0
        repo.update.assert_not_awaited()

    async def test_returns_count_of_emails_sent(self):
        vers = [_mock_verification(ver_id=f"ver-{i}") for i in range(3)]
        user = _mock_user()
        svc, repo = _make_svc(abandoned_verifications=vers)

        mock_msg_svc = MagicMock()
        mock_msg_svc.send_abandonment_recovery = AsyncMock()
        mock_user_repo = MagicMock()
        mock_user_repo.get_model = AsyncMock(return_value=user)

        with patch("main.app.domain.verification.service.di") as mock_di:
            from main.app.domain.message.verification_messages import VerificationMessages
            from main.app.domain.user.repo import UserRepo
            mock_di.__getitem__ = MagicMock(side_effect=lambda cls: (
                mock_msg_svc if cls == VerificationMessages else mock_user_repo
            ))

            count = await svc.send_abandonment_emails()

        assert count == 3

    async def test_continues_on_individual_failure(self):
        ver1 = _mock_verification(ver_id="ver-1")
        ver2 = _mock_verification(ver_id="ver-2")
        user = _mock_user()
        svc, repo = _make_svc(abandoned_verifications=[ver1, ver2])

        call_count = 0

        async def _send_with_first_failure(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Send failed")

        mock_msg_svc = MagicMock()
        mock_msg_svc.send_abandonment_recovery = AsyncMock(side_effect=_send_with_first_failure)
        mock_user_repo = MagicMock()
        mock_user_repo.get_model = AsyncMock(return_value=user)

        with patch("main.app.domain.verification.service.di") as mock_di:
            from main.app.domain.message.verification_messages import VerificationMessages
            from main.app.domain.user.repo import UserRepo
            mock_di.__getitem__ = MagicMock(side_effect=lambda cls: (
                mock_msg_svc if cls == VerificationMessages else mock_user_repo
            ))

            count = await svc.send_abandonment_emails()

        # First fails (counted as not sent), second succeeds
        assert count == 1
