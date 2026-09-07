"""CallbackService.update_callback__handle_time — the no-match branch.

A provider re-posting an event we already marked handled, or posting one we never
recorded, leaves the criterion search empty. That branch used to end in a bare `raise`
sitting in an `else:` rather than an `except:`, so Python raised
``RuntimeError: No active exception to reraise`` — a message about the interpreter's
state, not about the callback, and one that maps to a 500 rather than the 404 the
condition actually is. The test pins the exception type, because the failure it replaces
looked like a crash in our own code.
"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.config.settings import IntegratedPlatform
from main.appodus_utils.domain.webhook.callback.model import CallbackType, CreateCallbackDto
from main.appodus_utils.domain.webhook.callback.service import CallbackService
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import ResourceNotFoundException


@pytest.fixture(autouse=True)
def mock_db_session():
    """`CallbackService`'s methods are `@transactional`, so they need a session in context."""
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


def _service(matches):
    svc = object.__new__(CallbackService)
    svc._callback_repo = MagicMock()
    svc._callback_repo.get_by_criterion = AsyncMock(return_value=matches)
    svc._callback_repo.update = AsyncMock(return_value=None)
    svc._callback_validator = MagicMock()
    return svc


def _event():
    return CreateCallbackDto(
        platform=IntegratedPlatform.ZOHO_DOC_SIGN,
        event_type=CallbackType.CONTRACT_SIGNED,
        external_id="ext-1",
        payload={"any": "thing"},
        handle_from_time=datetime.now(timezone.utc),
    )


async def test_raises_not_found_when_no_unhandled_callback_matches():
    svc = _service(matches=[])

    with pytest.raises(ResourceNotFoundException) as exc:
        await svc.update_callback__handle_time(_event())

    # The identifying triple must be in the message: a 404 that does not say which event
    # went missing sends whoever is on call back to the provider's dashboard to guess.
    assert "zoho_doc_sign" in str(exc.value)
    assert "CONTRACT_SIGNED" in str(exc.value)
    assert "ext-1" in str(exc.value)


async def test_updates_the_matched_callback_and_reports_success():
    match = MagicMock()
    match.id = "cb-1"
    svc = _service(matches=[match])

    assert await svc.update_callback__handle_time(_event()) is True
    svc._callback_repo.update.assert_awaited_once()
    assert svc._callback_repo.update.await_args.args[0] == "cb-1"
