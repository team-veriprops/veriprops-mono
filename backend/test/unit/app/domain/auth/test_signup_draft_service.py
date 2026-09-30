"""SignupDraftService — a half-finished signup resumes where the user left off (§1.1).

Drafts are keyed by the email, case-insensitively, and expire after the configured TTL. A
draft whose payload can't be decoded resumes from an empty payload rather than failing the
signup page.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from main.app.config.settings import settings
from main.app.domain.user.auth.signup_draft.service import SignupDraftService
from test.utils.db_session import mock_db_session  # noqa: F401  (autouse fixture)

_UPDATED = datetime(2026, 9, 30, 12, tzinfo=timezone.utc)


def _row(payload='{"firstname": "Ada"}', date_updated=_UPDATED):
    return SimpleNamespace(id="d1", email="ada@example.com", step=2, payload=payload,
                           date_updated=date_updated, date_created=_UPDATED - timedelta(hours=1))


def _service(active=None):
    svc = object.__new__(SignupDraftService)
    svc._signup_draft_repo = MagicMock()
    svc._signup_draft_repo.get_active_by_email = AsyncMock(return_value=active)
    svc._signup_draft_repo.upsert_active = AsyncMock(side_effect=lambda **kw: SimpleNamespace(
        id="d1", date_updated=None, date_created=_UPDATED, **kw,
    ))
    svc._signup_draft_repo.soft_delete = AsyncMock()
    return svc


async def test_saving_keys_the_draft_by_lowercased_email_and_expires_it_after_the_ttl():
    svc = _service()

    draft = await svc.upsert(email="Ada@Example.com", step=2, payload={"firstname": "Ada"})

    kwargs = svc._signup_draft_repo.upsert_active.call_args.kwargs
    assert kwargs["email"] == "ada@example.com"
    ttl = kwargs["expires_at"] - datetime.now(timezone.utc)
    assert timedelta(days=settings.SIGNUP_DRAFT_TTL_DAYS) - ttl < timedelta(minutes=1)
    assert (draft.email, draft.step, draft.payload) == ("ada@example.com", 2, {"firstname": "Ada"})
    assert draft.date_updated == _UPDATED  # a fresh row has only its creation time


async def test_resuming_reads_the_draft_by_lowercased_email():
    svc = _service(active=_row())

    draft = await svc.get("ADA@example.com")

    svc._signup_draft_repo.get_active_by_email.assert_awaited_once_with("ada@example.com")
    assert draft.payload == {"firstname": "Ada"}


async def test_no_draft_resumes_as_none():
    assert await _service().get("ada@example.com") is None


async def test_a_malformed_payload_resumes_empty_instead_of_failing():
    draft = await _service(active=_row(payload="{not json")).get("ada@example.com")

    assert draft.payload == {}


async def test_discarding_soft_deletes_the_live_draft_only_when_there_is_one():
    svc = _service(active=_row())
    await svc.discard("Ada@example.com")
    svc._signup_draft_repo.soft_delete.assert_awaited_once_with("d1")

    empty = _service()
    await empty.discard("ada@example.com")
    empty._signup_draft_repo.soft_delete.assert_not_awaited()
