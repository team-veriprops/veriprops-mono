"""Writes that used to read-then-create, now safe when two requests arrive together.

Each site either goes through one race-free statement (`insert_or_get` / `upsert`, keyed on
the unique guard) or, where no index can describe the rule, makes concurrent writers take
turns with a transaction-scoped advisory lock. Service-specific behaviour is pinned in each
service's own tests; this file covers the cross-cutting cases.
"""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import UserAlreadyExistsException


@pytest.fixture(autouse=True)
def session():
    s = MagicMock()
    s.in_transaction.return_value = False

    @asynccontextmanager
    async def _begin():
        yield

    s.begin = _begin
    s.flush = AsyncMock()
    s.execute = AsyncMock()
    token = db_session_ctx.set(s)
    yield s
    db_session_ctx.reset(token)


# ── Accounts ──────────────────────────────────────────────────────────


async def test_a_signup_that_loses_the_email_race_is_told_it_exists():
    from main.app.domain.user.models import CreateUserDto
    from main.app.domain.user.service import UserService
    from main.appodus_utils.db.types.money import TransactionCurrency

    svc = object.__new__(UserService)
    svc._user_validator = MagicMock(should_not_exist_by_email=AsyncMock())  # the check saw nothing
    svc._user_repo = MagicMock(insert_or_get=AsyncMock(return_value=(SimpleNamespace(id="winner"), False)))

    with pytest.raises(UserAlreadyExistsException):
        await svc.create_user(CreateUserDto(
            first_name="Ada", last_name="W", email="ada@example.com", phone="8012345678",
            phone_country_code="NG", phone_dial_code="+234", country_of_residence="NG",
            timezone="Africa/Lagos", preferred_currency=TransactionCurrency.NGN,
        ))
    assert svc._user_repo.insert_or_get.await_args.args[1] == ["email_normalized"]


def _oauth_service():
    from main.app.domain.user.auth.service import AuthService

    svc = object.__new__(AuthService)
    svc._user_service = MagicMock()
    svc._oauth_identity_service = MagicMock()
    return svc


_OAUTH_ARGS = ("GOOGLE", "sub-1", "ada@example.com", "Ada", "W", None, {}, None)


async def test_a_double_fired_oauth_callback_signs_in_as_the_winner():
    svc = _oauth_service()
    winner = SimpleNamespace(id="u-winner")
    identity = SimpleNamespace(user_id="u-winner")
    # First pass: nothing found, and creating the account loses the race.
    svc._oauth_identity_service.get_oauth_identity = AsyncMock(side_effect=[None, identity])
    svc._user_service.get_user_by_email = AsyncMock(return_value=None)
    svc._user_service.create_user = AsyncMock(side_effect=UserAlreadyExistsException(email="ada@example.com"))
    svc._user_service.get_user_model = AsyncMock(return_value=winner)

    user, is_new = await svc.find_or_create_oauth_user(*_OAUTH_ARGS)

    assert (user, is_new) == (winner, False)
    svc._user_service.create_user.assert_awaited_once()


async def test_a_real_password_account_clash_still_raises():
    svc = _oauth_service()
    svc._oauth_identity_service.get_oauth_identity = AsyncMock(return_value=None)
    svc._user_service.get_user_by_email = AsyncMock(return_value=SimpleNamespace(id="u-1", password_hash="h"))

    with pytest.raises(UserAlreadyExistsException):
        await svc.find_or_create_oauth_user(*_OAUTH_ARGS)


# ── Writes serialised by an advisory lock ─────────────────────────────


@pytest.fixture
def lock(monkeypatch):
    held = AsyncMock()

    def _patch(module):
        monkeypatch.setattr(module, "advisory_xact_lock", held)
        return held

    return _patch


async def test_replacing_a_tiers_line_items_takes_the_tiers_lock(lock):
    import main.app.domain.verification.pricing_config.service as module
    from main.app.domain.verification.pricing_config.service import PricingConfigService
    from main.app.core.state.status import VerificationTier

    held = lock(module)
    svc = object.__new__(PricingConfigService)
    svc._line_items = MagicMock(list_for_tier=AsyncMock(return_value=[]), create_return_model=AsyncMock())
    svc._audit = MagicMock()

    await svc.set_line_items(VerificationTier.BASIC, [], "admin-1")

    held.assert_awaited_once_with("pricing_line_items:BASIC")


async def test_replacing_a_tiers_weight_map_takes_the_tiers_lock(lock):
    import main.app.domain.verification.scoring.service as module
    from main.app.core.state.status import AgentRole
    from main.app.domain.verification.scoring.service import TrustScoreWeightService
    from main.app.core.state.status import VerificationTier

    held = lock(module)
    svc = object.__new__(TrustScoreWeightService)
    svc._weight_repo = MagicMock(upsert=AsyncMock(), list_for_tier=AsyncMock(return_value=[]))
    svc._audit = MagicMock()

    await svc.set_tier_weights(
        VerificationTier.STANDARD, {AgentRole.REGISTRY: 40, AgentRole.FIELD: 30, AgentRole.SURVEYOR: 30}, "admin-1",
    )

    held.assert_awaited_once_with("trust_weights:STANDARD")
    assert all(c.kwargs == {"unique_index": "uq_trust_weight_tier_role"} for c in svc._weight_repo.upsert.await_args_list)


async def test_replacing_an_agents_coverage_takes_the_agents_lock(lock):
    import main.app.domain.user.agent.reputation.service as module
    from main.app.domain.user.agent.reputation.service import AgentReputationService

    held = lock(module)
    svc = object.__new__(AgentReputationService)
    svc._coverage = MagicMock(list_for_user=AsyncMock(return_value=[]), create=AsyncMock())
    svc._config = MagicMock(get_int=AsyncMock(return_value=5))
    svc._audit = MagicMock()

    await svc.set_coverage("a-1", [])

    held.assert_awaited_once_with("agent_coverage:a-1")


async def test_saving_an_application_draft_takes_the_applicants_lock(lock):
    import main.app.domain.user.agent.application_draft.service as module
    from main.app.domain.user.agent.application_draft.models import SaveAgentApplicationDraftDto
    from main.app.domain.user.agent.application_draft.service import AgentApplicationDraftService

    held = lock(module)
    svc = object.__new__(AgentApplicationDraftService)
    svc._draft_repo = MagicMock(get_active_for_user=AsyncMock(return_value=None), create=AsyncMock())

    await svc.save_draft("u-1", SaveAgentApplicationDraftDto(step=1, payload={}))

    held.assert_awaited_once_with("agent_application_draft:u-1")


async def test_requesting_erasure_takes_the_accounts_lock(lock):
    import main.app.domain.compliance.erasure.service as module
    from main.app.domain.compliance.erasure.service import ErasureService
    from main.appodus_utils.exception.exceptions import InvalidResourceStateException

    held = lock(module)
    svc = object.__new__(ErasureService)
    svc._users = MagicMock(get_model=AsyncMock(return_value=SimpleNamespace(id="u-1")))
    svc._erasure_repo = MagicMock(get_open_for_user=AsyncMock(return_value=SimpleNamespace(id="open")))

    with pytest.raises(InvalidResourceStateException):
        await svc.request("u-1", "u-1", None)

    held.assert_awaited_once_with("erasure_request:u-1")


# ── Smaller get-or-create sites ───────────────────────────────────────


async def test_number_health_is_created_once_per_number(monkeypatch):
    import main.app.domain.channel.whatsapp.analytics.health_service as module
    from main.app.domain.channel.whatsapp.analytics.health_service import WhatsAppNumberHealthService

    svc = object.__new__(WhatsAppNumberHealthService)
    row = SimpleNamespace(quality_rating=None, messaging_limit_tier=None, last_synced_at=None, sync_error=None)
    svc._health = MagicMock(insert_or_get=AsyncMock(return_value=(row, False)), _session=MagicMock())
    monkeypatch.setattr(module, "whatsapp_number_directory",
                        lambda: MagicMock(fetch_number_health=AsyncMock(side_effect=RuntimeError("offline"))))

    await svc.sync()

    assert svc._health.insert_or_get.await_args.kwargs == {
        "unique_index": "uq_whatsapp_number_health_phone_number_id"
    }


async def test_an_assistant_session_is_opened_once_per_conversation():
    from main.app.domain.communication.assistant.session.service import AssistantSessionService

    svc = object.__new__(AssistantSessionService)
    winner = SimpleNamespace(id="s-1")
    svc._assistant_session_repo = MagicMock(
        get_by_conversation=AsyncMock(return_value=None),
        insert_or_get=AsyncMock(return_value=(winner, False)),
    )

    session = await svc.get_or_open(SimpleNamespace(id="c-1"))

    assert session is winner
    assert svc._assistant_session_repo.insert_or_get.await_args.args[1] == ["conversation_id"]


async def test_a_referral_link_is_created_once_per_user():
    from main.app.domain.referral.service import ReferralService

    svc = object.__new__(ReferralService)
    winner = SimpleNamespace(id="r-1", code="ABC")
    svc._referrals = MagicMock(
        get_for_referrer=AsyncMock(return_value=None),
        get_by_code=AsyncMock(return_value=None),
        insert_or_get=AsyncMock(return_value=(winner, False)),
    )

    assert await svc.get_or_create_link("u-1") is winner
    assert svc._referrals.insert_or_get.await_args.args[1] == ["referrer_user_id"]
