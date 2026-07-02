"""Dojah KYC provider (PRD §3.1 — default real provider, behind the facade).

Selected only when ``settings.KYC_PROVIDER == DOJAH``. Instantiation stays cheap
and credential-free so bootstrap can register every provider subclass regardless
of the active selection; credentials are validated lazily on first real call.

Wiring the live Dojah endpoints (``/api/v1/kyc/bvn``, ``/api/v1/kyc/photoid/verify``)
requires live credentials and is intentionally gated: until enabled and tested
against a Dojah sandbox, calls raise so no unverified network path masquerades as
a passing identity check. Local/test/dev use the deterministic StubKycProvider.
"""
from __future__ import annotations

from kink import inject

from main.app.config.settings import settings
from main.appodus_utils.exception.exceptions import AppodusBaseException
from main.appodus_utils.integrations.kyc.interface import IKycProvider
from main.appodus_utils.integrations.kyc.models import (
    BvnVerificationRequest,
    GovIdVerificationRequest,
    KycProvider,
    KycVerificationResult,
)


@inject
class DojahKycProvider(IKycProvider):
    @property
    def platform(self) -> KycProvider:
        return KycProvider.DOJAH

    def _require_credentials(self) -> None:
        if not settings.DOJAH_APP_ID or not settings.DOJAH_PRIVATE_KEY:
            raise AppodusBaseException(
                message="Dojah KYC provider is selected but credentials are not configured.",
            )
        # The live Dojah HTTP integration is gated pending sandbox verification.
        raise AppodusBaseException(
            message="Dojah KYC integration is not yet enabled; set KYC_PROVIDER=STUB for automation.",
        )

    async def verify_bvn(self, payload: BvnVerificationRequest) -> KycVerificationResult:
        self._require_credentials()

    async def verify_id_document(self, payload: GovIdVerificationRequest) -> KycVerificationResult:
        self._require_credentials()

    async def get_status(self, provider_ref: str) -> KycVerificationResult:
        self._require_credentials()
