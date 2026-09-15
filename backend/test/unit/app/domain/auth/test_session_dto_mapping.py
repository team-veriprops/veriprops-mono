"""Unit tests for _user_to_session_dto (backend/main/app/domain/user/auth/session/service.py).

Verifies the User → SessionUserDto mapping, in particular that
has_started_verification (§ first-login new-verification auto-launch gate) is
read straight off the User row.
"""
from types import SimpleNamespace

from main.app.domain.user.auth.session.models import UserType
from main.app.domain.user.auth.session.service import _user_to_session_dto
from main.app.domain.user.models import OAUTH_PLACEHOLDER_PHONE, AccountStatus


def _make_user(**overrides):
    base = dict(
        id="uid-1",
        first_name="Ada",
        last_name="Obi",
        email="ada@example.com",
        email_verified=True,
        phone="8012345678",
        phone_country_code="NG",
        phone_dial_code="+234",
        phone_verified=True,
        country_of_residence="NG",
        timezone="Africa/Lagos",
        preferred_currency="NGN",
        user_type=UserType.USER.value,
        personas=[],
        admin_sub_role=None,
        trust_status="UNTRUSTED",
        account_status=AccountStatus.ACTIVE.value,
        avatar_url=None,
        date_created="2026-07-18T00:00:00+00:00",
        has_started_verification=False,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_maps_has_started_verification_true():
    user = _make_user(has_started_verification=True)
    dto = _user_to_session_dto(user, has_password=True, linked=[])
    assert dto.has_started_verification is True


def test_maps_has_started_verification_false():
    user = _make_user(has_started_verification=False)
    dto = _user_to_session_dto(user, has_password=True, linked=[])
    assert dto.has_started_verification is False


def test_oauth_placeholder_phone_is_exposed_as_no_phone():
    # Clients render "no number yet" rather than a synthetic one they would need to recognise.
    user = _make_user(phone=OAUTH_PLACEHOLDER_PHONE, phone_verified=False)
    dto = _user_to_session_dto(user, has_password=False, linked=[])
    assert dto.phone == ""


def test_real_phone_is_passed_through():
    dto = _user_to_session_dto(_make_user(), has_password=True, linked=[])
    assert dto.phone == "8012345678"
