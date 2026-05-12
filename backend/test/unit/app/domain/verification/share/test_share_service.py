"""Unit tests for ShareService (S43)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.verification.share.models import (
    CreateShareDto,
    ShareMode,
)
from main.app.domain.verification.share.service import ShareService
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import (
    ForbiddenException,
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


def _mock_share_link(
    link_id="sl-1", verification_id="ver-1", mode=ShareMode.LINK_ONLY,
    created_by="cust-1", revoked_at=None, expires_at=None,
):
    s = MagicMock()
    s.id = link_id
    s.verification_id = verification_id
    s.mode = mode.value
    s.token = "abc123token"
    s.expires_at = expires_at
    s.revoked_at = revoked_at
    s.created_by = created_by
    s.date_created = str(datetime.now(timezone.utc))
    return s


def _make_svc(link=None):
    repo = MagicMock()
    repo.create = AsyncMock(return_value=link or _mock_share_link())
    repo.get_model = AsyncMock(return_value=link or _mock_share_link())
    repo.update = AsyncMock()
    repo.get_by_token = AsyncMock(return_value=link or _mock_share_link())

    recipient_repo = MagicMock()
    recipient_repo.create = AsyncMock()
    recipient_repo.update = AsyncMock()

    svc = ShareService(repo=repo, recipient_repo=recipient_repo)
    return svc, repo, recipient_repo


class TestCreate:
    async def test_generates_non_empty_token(self):
        svc, repo, _ = _make_svc()

        await svc.create(
            "ver-1", "cust-1",
            CreateShareDto(mode=ShareMode.LINK_ONLY),
        )

        call_dto = repo.create.call_args[0][0]
        assert call_dto.token and len(call_dto.token) > 10

    async def test_named_recipient_without_email_raises(self):
        svc, _, _ = _make_svc()

        with pytest.raises(ValidationException, match="recipient_email"):
            await svc.create(
                "ver-1", "cust-1",
                CreateShareDto(mode=ShareMode.NAMED_RECIPIENT, recipient_email=None),
            )

    async def test_named_recipient_with_email_creates_recipient_row(self):
        svc, _, recipient_repo = _make_svc()

        await svc.create(
            "ver-1", "cust-1",
            CreateShareDto(mode=ShareMode.NAMED_RECIPIENT, recipient_email="buyer@example.com"),
        )

        recipient_repo.create.assert_called_once()


class TestRevoke:
    async def test_sets_revoked_at(self):
        link = _mock_share_link(revoked_at=None)
        svc, repo, _ = _make_svc(link=link)

        await svc.revoke("sl-1", "cust-1")

        repo.update.assert_called_once()
        call_dto = repo.update.call_args[0][1]
        assert call_dto.revoked_at is not None

    async def test_different_owner_raises(self):
        link = _mock_share_link(created_by="owner-1")
        svc, _, _ = _make_svc(link=link)

        with pytest.raises(ForbiddenException):
            await svc.revoke("sl-1", "different-user")

    async def test_link_not_found_raises(self):
        svc, repo, _ = _make_svc()
        repo.get_model = AsyncMock(return_value=None)

        with pytest.raises(ResourceNotFoundException):
            await svc.revoke("missing-sl", "cust-1")


class TestGetByToken:
    async def test_revoked_link_raises_forbidden(self):
        link = _mock_share_link(revoked_at=str(datetime.now(timezone.utc)))
        svc, repo, _ = _make_svc(link=link)
        repo.get_by_token = AsyncMock(return_value=link)

        with pytest.raises(ForbiddenException, match="revoked"):
            await svc.get_by_token("abc123token")

    async def test_expired_link_raises_validation_error(self):
        past = str(datetime.now(timezone.utc) - timedelta(days=1))
        link = _mock_share_link(expires_at=past, revoked_at=None)
        svc, repo, _ = _make_svc(link=link)
        repo.get_by_token = AsyncMock(return_value=link)

        with pytest.raises(ValidationException, match="expired"):
            await svc.get_by_token("abc123token")

    async def test_valid_link_returns_dto(self):
        link = _mock_share_link(revoked_at=None, expires_at=None)
        svc, repo, _ = _make_svc(link=link)
        repo.get_by_token = AsyncMock(return_value=link)

        result = await svc.get_by_token("abc123token")
        assert result.id == "sl-1"
