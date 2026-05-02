"""Settings-driven KYC provider factory."""
from __future__ import annotations

from kink import di

from main.app.config.settings import settings
from main.app.domain.user.agent.kyc.interface import KycProvider
from main.app.domain.user.agent.kyc.providers.dojah import DojahKycProvider
from main.app.domain.user.agent.kyc.providers.mono import MonoKycProvider
from main.app.domain.user.agent.kyc.providers.stub import StubKycProvider


def _build_provider() -> KycProvider:
    name = (getattr(settings, "KYC_PROVIDER", None) or "STUB").upper()
    if name == "MONO":
        return MonoKycProvider()
    if name == "DOJAH":
        return DojahKycProvider()
    return StubKycProvider()


# Register a singleton against the abstract type so services can resolve
# `di[KycProvider]`.
di[KycProvider] = _build_provider()
