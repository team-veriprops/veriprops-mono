"""Services that migration 0018's narrowed and added unique guards rely on.

- A signup draft is one statement keyed on the live email: an abandoned (soft-deleted) or
  expired draft never blocks a new one, and two concurrent saves can't both insert.
- An OAuth signup's placeholder phone is not a real number, so it is never stored as one.
  Every OAuth user used to share `+2340000000000`.
- An upgrade's idempotency key is unique only while that upgrade is PENDING.
"""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from main.app.domain.user.auth.signup_draft.repo import SignupDraftRepo
from main.app.domain.user.models import OAUTH_PLACEHOLDER_PHONE
from main.app.domain.user.service import UserService
from main.app.domain.verification.upgrade.repo import UpgradeRepo
from main.appodus_utils import Utils
from main.appodus_utils.db.session import db_session_ctx


@pytest.fixture(autouse=True)
def session():
    s = MagicMock()
    s.in_transaction.return_value = False

    @asynccontextmanager
    async def _begin():
        yield

    s.begin = _begin
    s.flush = AsyncMock()
    s.statements = []

    async def _execute(stmt):
        s.statements.append(stmt)
        result = MagicMock()
        result.scalar_one.return_value = MagicMock()
        result.scalar_one_or_none.return_value = None
        return result

    s.execute = AsyncMock(side_effect=_execute)
    token = db_session_ctx.set(s)
    yield s
    db_session_ctx.reset(token)


def _sql(stmt) -> str:
    return " ".join(str(stmt.compile(dialect=postgresql.dialect())).split())


# ── Signup drafts ─────────────────────────────────────────────────────


async def test_saving_a_draft_is_one_upsert_on_the_live_email(session):
    repo = SignupDraftRepo(db=None)

    await repo.upsert_active(email="ada@example.com", step=2, payload="{}", expires_at=Utils.datetime_now())

    sql = _sql(session.statements[0])
    assert sql.startswith("INSERT INTO signup_drafts")
    assert "ON CONFLICT (email) WHERE deleted = false DO UPDATE SET step = excluded.step" in sql
    assert "expires_at = excluded.expires_at" in sql and "payload = excluded.payload" in sql
    assert "RETURNING" in sql


# ── OAuth placeholder phone ───────────────────────────────────────────


def _user_service():
    svc = object.__new__(UserService)
    svc._user_validator = MagicMock(should_not_exist_by_email=AsyncMock())
    svc._user_repo = MagicMock(insert_or_get=AsyncMock(
        side_effect=lambda values, conflict_columns: (SimpleNamespace(**values), True)
    ))
    return svc


def _create_dto(phone: str):
    from main.app.domain.user.models import CreateUserDto
    from main.appodus_utils.db.types.money import TransactionCurrency

    return CreateUserDto(
        first_name="Ada", last_name="W", email="ada@example.com", password_hash=None,
        phone=phone, phone_country_code="NG", phone_dial_code="+234",
        country_of_residence="NG", timezone="Africa/Lagos",
        preferred_currency=TransactionCurrency.NGN, personas=[],
    )


async def test_an_oauth_placeholder_phone_is_not_stored_as_a_number():
    stored = await _user_service().create_user(_create_dto(OAUTH_PLACEHOLDER_PHONE))
    assert stored.phone_e164 is None


async def test_a_real_phone_is_stored_in_e164():
    stored = await _user_service().create_user(_create_dto("8012345678"))
    assert stored.phone_e164 == "+2348012345678"


# ── Upgrade requests ──────────────────────────────────────────────────


async def test_an_upgrade_key_is_looked_up_among_pending_requests_only(session):
    await object.__new__(UpgradeRepo).get_pending_by_key("vid:PREMIUM")
    sql = _sql(session.statements[0])
    assert "upgrade_requests.idempotency_key = %(idempotency_key_1)s" in sql
    assert "upgrade_requests.status = %(status_1)s" in sql

