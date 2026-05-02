"""Stub KYC provider — deterministic outcomes for dev / test envs.

BVN verification: succeeds for any 11-digit BVN whose last digit is even;
fails otherwise.

Selfie match: succeeds with score 92 when the selfie payload is non-empty,
otherwise reports a low score.
"""
from __future__ import annotations

import uuid
from typing import Optional

from main.app.domain.user.agent.kyc.interface import (
    BvnVerificationResult,
    KycProvider,
    SelfieMatchResult,
)


class StubKycProvider(KycProvider):
    async def verify_bvn(self, bvn: str) -> BvnVerificationResult:
        digits = bvn.strip()
        if len(digits) != 11 or not digits.isdigit():
            return BvnVerificationResult(
                verified=False,
                verification_id=None,
                failure_reason="BVN must be 11 digits",
            )
        if int(digits[-1]) % 2 != 0:
            return BvnVerificationResult(
                verified=False,
                verification_id=None,
                failure_reason="BVN could not be verified",
            )
        return BvnVerificationResult(
            verified=True,
            verification_id=f"stub-{uuid.uuid4()}",
        )

    async def match_selfie(
        self,
        selfie_bytes: bytes,
        reference_image_bytes: Optional[bytes] = None,
    ) -> SelfieMatchResult:
        if not selfie_bytes:
            return SelfieMatchResult(matched=False, score=0, failure_reason="empty selfie payload")
        # Deterministic dev outcome.
        return SelfieMatchResult(matched=True, score=92)
