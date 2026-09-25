"""Unit tests for the self-service CUSTOMER persona grant (§3.2).

Signing up through the agent path grants `[AGENT]` alone, so such an account cannot open `/portal/*`
at all — the mirror of the hole a customer met when applying to become an agent. Taking up the
customer hat is a deliberate act from inside the product ("Verify a Property"), and it must work in
the session the user is already in: the grant reaches the database at once, but the route guard
reads the refresh token, so the endpoint rotates the session as well.

The persona is **not** a request parameter. This route grants CUSTOMER and nothing else, so no
client can claim a hat — AGENT stays reachable only by applying and being approved.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from main.app.config.settings import settings
from main.app.domain.user.auth import controller as auth_controller
from main.app.domain.user.auth.session.models import AuthSessionDto, UserPersona


def _request_with_refresh(token: str | None = "rt"):
    return SimpleNamespace(cookies={settings.AUTHJWT_REFRESH_COOKIE_KEY: token} if token else {})


def _wire(monkeypatch, *, personas_after):
    """Mock the collaborators the endpoint reaches and hand back the doubles to assert on."""
    granted_user = SimpleNamespace(id="u-1", personas=personas_after)
    # model_construct bypasses field validation — these tests care that the endpoint forwards the
    # session the rotation produced, not about its contents.
    session_dto = AuthSessionDto.model_construct()

    users = MagicMock()
    users.add_persona = AsyncMock(return_value=granted_user)
    monkeypatch.setattr(auth_controller, "user_service", users, raising=False)

    sessions = MagicMock()
    sessions.rotate_current_session = AsyncMock(return_value=session_dto)
    monkeypatch.setattr(auth_controller, "session_service", sessions)

    authorize = MagicMock()
    authorize.jwt_required = AsyncMock()
    authorize.get_jwt_subject = MagicMock(return_value="u-1")
    return users, sessions, authorize, session_dto


async def test_grants_the_customer_persona_and_returns_the_rotated_session(monkeypatch):
    users, sessions, authorize, session_dto = _wire(
        monkeypatch, personas_after=[UserPersona.AGENT, UserPersona.CUSTOMER],
    )

    result = await auth_controller.grant_customer_persona(_request_with_refresh(), authorize)

    users.add_persona.assert_awaited_once_with("u-1", UserPersona.CUSTOMER)
    sessions.rotate_current_session.assert_awaited_once()
    assert result.data is session_dto


async def test_rotation_is_handed_the_user_the_grant_returned(monkeypatch):
    """Rotating from a stale copy would mint the very personas the grant just changed."""
    granted = [UserPersona.AGENT, UserPersona.CUSTOMER]
    users, sessions, authorize, _ = _wire(monkeypatch, personas_after=granted)

    await auth_controller.grant_customer_persona(_request_with_refresh(), authorize)

    rotated_user = sessions.rotate_current_session.await_args[0][0]
    assert rotated_user is users.add_persona.return_value
    assert rotated_user.personas == granted


async def test_the_caller_must_be_signed_in(monkeypatch):
    _, _, authorize, _ = _wire(monkeypatch, personas_after=[UserPersona.CUSTOMER])

    await auth_controller.grant_customer_persona(_request_with_refresh(), authorize)

    authorize.jwt_required.assert_awaited_once()


async def test_granting_twice_is_a_no_op_that_still_returns_a_session(monkeypatch):
    """`add_persona` is idempotent, so a double-click must not be an error."""
    _, sessions, authorize, session_dto = _wire(
        monkeypatch, personas_after=[UserPersona.CUSTOMER],
    )

    first = await auth_controller.grant_customer_persona(_request_with_refresh(), authorize)
    second = await auth_controller.grant_customer_persona(_request_with_refresh(), authorize)

    assert first.data is session_dto and second.data is session_dto
    assert sessions.rotate_current_session.await_count == 2
