"""Dojah BVN-verification provider — TODO (PRD Open Q #15)."""
from __future__ import annotations

from typing import Optional

from main.app.domain.user.agent.kyc.interface import (
    BvnVerificationResult,
    KycProvider,
    SelfieMatchResult,
)


class DojahKycProvider(KycProvider):
    async def verify_bvn(self, bvn: str) -> BvnVerificationResult:
        raise NotImplementedError(
            "Dojah BVN provider not yet implemented — PRD Open Q #15"
        )

    async def match_selfie(
        self,
        selfie_bytes: bytes,
        reference_image_bytes: Optional[bytes] = None,
    ) -> SelfieMatchResult:
        raise NotImplementedError(
            "Dojah selfie-match not yet implemented — PRD Open Q #16"
        )
