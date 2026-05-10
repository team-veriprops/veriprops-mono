"""KYC provider contract."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BvnVerificationResult:
    verified: bool
    verification_id: Optional[str]
    failure_reason: Optional[str] = None
    provider: str = field(default="")


@dataclass
class SelfieMatchResult:
    matched: bool
    score: int  # 0–100
    failure_reason: Optional[str] = None


class KycProvider(ABC):
    @abstractmethod
    async def verify_bvn(self, bvn: str) -> BvnVerificationResult: ...

    @abstractmethod
    async def match_selfie(
        self,
        selfie_bytes: bytes,
        reference_image_bytes: Optional[bytes] = None,
    ) -> SelfieMatchResult: ...

    @abstractmethod
    async def submit_selfie(
        self,
        selfie_bytes: bytes,
        reference_bvn_last4: Optional[str] = None,
    ) -> str:
        """Initiate async selfie verification. Returns provider job/verification ID."""
        ...
