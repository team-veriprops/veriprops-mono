"""The portal route mirror (§12.2, §16.7) — the one place backend code spells a portal page."""
from main.app.core.links.portal import (
    VerificationPage,
    absolute_url,
    new_verification_path,
    verification_path,
)


def test_a_verification_page_mirrors_the_frontend_routes():
    # frontend/src/lib/routes.ts ROUTES.PORTAL.VERIFICATION_* — change both together.
    assert verification_path("v1") == "/portal/verifications/v1"
    assert verification_path("v1", VerificationPage.PAY) == "/portal/verifications/v1/pay"
    assert verification_path("v1", VerificationPage.REPORT) == "/portal/verifications/v1/report"
    assert new_verification_path() == "/portal/verifications/new"


def test_an_absolute_url_is_on_the_public_origin_without_a_double_slash(monkeypatch):
    from main.app.config.settings import settings

    monkeypatch.setattr(settings, "PUBLIC_APP_BASE_URL", "https://app.example/")

    assert absolute_url("/portal/verifications/v1") == "https://app.example/portal/verifications/v1"
