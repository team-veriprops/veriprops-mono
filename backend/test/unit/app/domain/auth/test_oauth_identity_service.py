"""OAuthIdentityService — a social sign-in is tied to one account by provider + subject (§1.2).

The provider's subject is the stable key: linking the same one twice returns the first link
rather than a duplicate, the raw profile is kept as text (never pickled), and unlinking one
provider leaves the others.
"""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from main.app.domain.user.auth.oauth.providers.models import SocialAuthProvider
from main.app.domain.user.auth.oauth.service import OAuthIdentityService
from test.utils.db_session import mock_db_session  # noqa: F401  (autouse fixture)


def _service(rows=()):
    """A service over an in-memory identity table."""
    table = list(rows)

    def _find(provider, subject):
        return next((r for r in table if r.provider == provider and r.subject == subject), None)

    async def _create(dto):
        table.append(SimpleNamespace(**dto.model_dump()))

    svc = object.__new__(OAuthIdentityService)
    svc._oauth_repo = MagicMock()
    svc._oauth_repo.get_by_provider_subject = AsyncMock(side_effect=_find)
    svc._oauth_repo.create = AsyncMock(side_effect=_create)
    svc._oauth_repo.get_by_criterion = AsyncMock(side_effect=lambda dto: [r for r in table if r.user_id == dto.user_id])
    svc._oauth_repo.soft_delete_by_criterion = AsyncMock()
    return svc, table


async def test_linking_stores_the_provider_subject_and_profile_as_text():
    svc, table = _service()

    identity = await svc.link_oauth("u1", SocialAuthProvider.GOOGLE, "sub-1", email="ada@example.com", raw_profile={"name": "Ada"})

    assert (identity.user_id, identity.provider, identity.subject) == ("u1", SocialAuthProvider.GOOGLE, "sub-1")
    assert json.loads(identity.raw_profile) == {"name": "Ada"}
    assert len(table) == 1


async def test_linking_a_subject_already_linked_returns_that_link_without_a_duplicate():
    first = SimpleNamespace(user_id="u1", provider=SocialAuthProvider.GOOGLE, subject="sub-1")
    svc, table = _service([first])

    assert await svc.link_oauth("u1", SocialAuthProvider.GOOGLE, "sub-1") is first
    svc._oauth_repo.create.assert_not_awaited()


async def test_the_same_subject_at_another_provider_is_a_separate_identity():
    svc, _ = _service([SimpleNamespace(user_id="u1", provider=SocialAuthProvider.GOOGLE, subject="sub-1")])

    assert await svc.get_oauth_identity(SocialAuthProvider.APPLE, "sub-1") is None


async def test_lists_the_providers_linked_to_a_user():
    svc, _ = _service([
        SimpleNamespace(user_id="u1", provider=SocialAuthProvider.GOOGLE, subject="a"),
        SimpleNamespace(user_id="u1", provider=SocialAuthProvider.APPLE, subject="b"),
        SimpleNamespace(user_id="u2", provider=SocialAuthProvider.FACEBOOK, subject="c"),
    ])

    assert await svc.list_linked_providers("u1") == [SocialAuthProvider.GOOGLE, SocialAuthProvider.APPLE]


async def test_unlinking_removes_only_that_provider_for_that_user():
    svc, _ = _service()

    await svc.unlink_oauth("u1", SocialAuthProvider.APPLE)

    criterion = svc._oauth_repo.soft_delete_by_criterion.call_args.args[0]
    assert (criterion.user_id, criterion.provider) == ("u1", SocialAuthProvider.APPLE.value)
