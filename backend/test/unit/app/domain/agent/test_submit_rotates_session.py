"""Submitting an agent application takes effect in the session that submitted it (§3.1/§3.2).

`submit_application` grants the AGENT persona additively, but the caller's tokens were minted before
it — and the frontend route guard reads the refresh token, which a plain refresh does not re-mint.
Without rotating here, an applicant is pushed at the agent dashboard and bounced straight back by
the guard, with nothing to tell them why.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from main.app.config.settings import settings
from main.app.domain.user.agent import controller as agent_controller
from main.app.domain.user.agent.models import AgentApplicationStatusDto


def _request_with_refresh(token: str | None = "rt"):
    return SimpleNamespace(
        cookies={settings.AUTHJWT_REFRESH_COOKIE_KEY: token} if token else {},
        headers={},
        client=SimpleNamespace(host="127.0.0.1"),
    )


def _wire(monkeypatch):
    status_dto = AgentApplicationStatusDto.model_construct()

    agents = MagicMock()
    agents.submit_application = AsyncMock(return_value=status_dto)
    monkeypatch.setattr(agent_controller, "agent_service", agents)

    granted_user = SimpleNamespace(id="u-1", personas=["AGENT"])
    users = MagicMock()
    users.get_user_model = AsyncMock(return_value=granted_user)
    monkeypatch.setattr(agent_controller, "user_service", users, raising=False)

    sessions = MagicMock()
    sessions.rotate_current_session = AsyncMock()
    monkeypatch.setattr(agent_controller, "session_service", sessions, raising=False)

    authorize = MagicMock()
    authorize.jwt_required = AsyncMock()
    authorize.get_jwt_subject = MagicMock(return_value="u-1")
    return agents, users, sessions, authorize, status_dto, granted_user


async def test_submitting_rotates_the_session_onto_the_granted_persona(monkeypatch):
    agents, users, sessions, authorize, status_dto, granted_user = _wire(monkeypatch)

    result = await agent_controller.submit_application(
        MagicMock(), _request_with_refresh(), authorize,
    )

    agents.submit_application.assert_awaited_once()
    # Re-read after the grant: the user object the request started with predates the new persona.
    users.get_user_model.assert_awaited_once_with("u-1")
    sessions.rotate_current_session.assert_awaited_once()
    assert sessions.rotate_current_session.await_args[0][0] is granted_user
    # The response is still the application's status — rotation is a side effect, not the payload.
    assert result.data is status_dto


async def test_a_failed_rotation_never_costs_the_applicant_their_application(monkeypatch):
    """The application is filed either way; a rotation failure only delays the persona to next
    sign-in, which is exactly where it used to take effect."""
    agents, _, sessions, authorize, status_dto, _ = _wire(monkeypatch)
    sessions.rotate_current_session = AsyncMock(side_effect=RuntimeError("cookie mint failed"))

    result = await agent_controller.submit_application(
        MagicMock(), _request_with_refresh(), authorize,
    )

    assert result.data is status_dto
