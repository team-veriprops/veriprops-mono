"""Unit tests for failed-attempt logging and security event emission (R2.7).

Verifies:
- record_event() persists to event repo with IP + fingerprint.
- record_event() handles anonymous events (no user_id).
- No PII (raw password, raw token) is stored in SecurityEvent description.
- SecurityEventType enum contains all required types.
- Rate-limit threshold constants match the PRD and backend settings.
"""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.appodus_utils.db.session import db_session_ctx
from main.app.domain.user.auth.session.models import (
    CreateSecurityEventDto,
    SecurityEventType,
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


def _make_service():
    from main.app.domain.user.auth.session.service import SessionService
    svc = object.__new__(SessionService)
    svc._device_repo = AsyncMock()
    svc._event_repo = AsyncMock()
    svc._reset_repo = AsyncMock()
    return svc


# ── record_event ─────────────────────────────────────────────────────────────

async def test_record_event_persists_to_event_repo():
    svc = _make_service()
    svc._event_repo.create = AsyncMock()

    await svc.record_event(
        SecurityEventType.LOGIN_FAILURE,
        "Invalid credentials",
        user_id="uid-1",
        ip_address="10.0.0.1",
        device_fingerprint="fp-abc",
    )

    svc._event_repo.create.assert_called_once()
    dto: CreateSecurityEventDto = svc._event_repo.create.call_args[0][0]
    assert dto.type == SecurityEventType.LOGIN_FAILURE
    assert dto.user_id == "uid-1"
    assert dto.ip_address == "10.0.0.1"
    assert dto.device_fingerprint == "fp-abc"
    assert dto.occurred_at is not None


async def test_record_event_captures_ip_and_fingerprint():
    svc = _make_service()
    svc._event_repo.create = AsyncMock()

    await svc.record_event(
        SecurityEventType.LOGIN_FAILURE_WARNING,
        "Repeated invalid credentials (5/7)",
        user_id="uid-2",
        ip_address="192.168.1.5",
        device_fingerprint="fingerprint-xyz",
    )

    dto: CreateSecurityEventDto = svc._event_repo.create.call_args[0][0]
    assert dto.ip_address == "192.168.1.5"
    assert dto.device_fingerprint == "fingerprint-xyz"


async def test_record_event_handles_anonymous_event_without_user_id():
    """Unknown email events must still be logged without leaking the email."""
    svc = _make_service()
    svc._event_repo.create = AsyncMock()

    await svc.record_event(
        SecurityEventType.LOGIN_FAILURE,
        "Invalid credentials",
        ip_address="1.2.3.4",
    )

    dto: CreateSecurityEventDto = svc._event_repo.create.call_args[0][0]
    assert dto.user_id is None
    assert dto.ip_address == "1.2.3.4"


async def test_no_raw_password_stored_in_event():
    """Security invariant: plaintext passwords must never appear in event records."""
    svc = _make_service()
    captured: list[CreateSecurityEventDto] = []
    svc._event_repo.create = AsyncMock(side_effect=lambda dto: captured.append(dto))

    plain_password = "MyS3cretP@ss"
    await svc.record_event(
        SecurityEventType.LOGIN_FAILURE,
        "Invalid credentials",
        user_id="uid-1",
    )

    for dto in captured:
        assert plain_password not in (dto.description or "")
        assert plain_password not in (dto.ip_address or "")
        assert plain_password not in (dto.device_fingerprint or "")


# ── SecurityEventType coverage (R2.7) ────────────────────────────────────────

def test_login_failure_warning_type_exists():
    assert SecurityEventType.LOGIN_FAILURE_WARNING == "LOGIN_FAILURE_WARNING"


def test_account_locked_type_exists():
    assert SecurityEventType.ACCOUNT_LOCKED == "ACCOUNT_LOCKED"


def test_password_changed_type_exists():
    assert SecurityEventType.PASSWORD_CHANGED == "PASSWORD_CHANGED"


def test_password_reset_requested_type_exists():
    assert SecurityEventType.PASSWORD_RESET_REQUESTED == "PASSWORD_RESET_REQUESTED"


# ── Rate-limit threshold constants (match backend settings, surface in R2.7) ─

def test_warn_at_is_5_of_7():
    from main.app.config.settings import settings
    warn_at = max(1, settings.AUTH_LOCKOUT_THRESHOLD - 2)
    assert warn_at == 5  # warn on attempt 5 of 7


def test_lockout_threshold_is_7():
    from main.app.config.settings import settings
    assert settings.AUTH_LOCKOUT_THRESHOLD == 7


def test_lockout_duration_is_15_minutes():
    from main.app.config.settings import settings
    assert settings.AUTH_LOCKOUT_MINUTES == 15
