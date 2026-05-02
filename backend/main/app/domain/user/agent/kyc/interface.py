"""KYC provider contract."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class BvnVerificationResult:
    verified: bool
    verification_id: Optional[str]
    failure_reason: Optional[str] = None


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
