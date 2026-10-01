"""KYC provider facade (PRD §0.1, §3.1).

Swappable behind ``settings.KYC_PROVIDER``. Implementations wrap a third-party
identity provider (Dojah) or a deterministic stub for local/test automation.

Every check starts with liveness on the selfie. A provider that cannot be reached or will
not serve (credentials, wallet, rate limit) raises ``IntegrationException``: that is an
outage, never an applicant who failed KYC.
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
        """Primary path — liveness, then the selfie matched to the BVN's photo (PRD §3.1)."""
        ...

    @abstractmethod
    async def verify_id_document(self, payload: GovIdVerificationRequest) -> KycVerificationResult:
        """Fallback path — liveness, then NIN matched automatically; any other government ID
        (passport, driver's licence, voter's card) goes to a person."""
        ...
