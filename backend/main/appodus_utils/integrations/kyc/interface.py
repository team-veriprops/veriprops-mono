"""KYC provider facade (PRD §0.1, §3.1).

Swappable behind ``settings.KYC_PROVIDER``. Implementations wrap a third-party
identity provider (Dojah) or a deterministic stub for local/test automation.
"""
from abc import ABC, abstractmethod

from main.appodus_utils.integrations.kyc.models import (
    BvnVerificationRequest,
    GovIdVerificationRequest,
    KycProvider,
    KycVerificationResult,
)


class IKycProvider(ABC):
    @property
    @abstractmethod
    def platform(self) -> KycProvider:
        ...

    @abstractmethod
    async def verify_bvn(self, payload: BvnVerificationRequest) -> KycVerificationResult:
        """Primary path — BVN + provider-side liveness/face-match (PRD §3.1)."""
        ...

    @abstractmethod
    async def verify_id_document(self, payload: GovIdVerificationRequest) -> KycVerificationResult:
        """Fallback path — government ID (NIN / Passport / Driver's Licence / Voter's Card)."""
        ...

    @abstractmethod
    async def get_status(self, provider_ref: str) -> KycVerificationResult:
        """Re-fetch a verification's current outcome by its provider reference."""
        ...
