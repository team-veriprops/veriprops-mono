"""Deterministic KYC stub — the default provider in local/test/dev.

Mirrors the OTP_MODE determinism contract: identity checks resolve to a fixed,
predictable outcome so autonomous QA (Playwright + Claude Code) is reproducible.
Never hits a network. Selected whenever ``settings.KYC_PROVIDER == STUB``.

Outcome is keyed on the id number so tests can drive each branch:

- ``TEST_ID_FAILED``  → FAILED (score 10)
- ``TEST_ID_REVIEW``  → NEEDS_REVIEW (score below the review threshold)
- anything else       → VERIFIED (score 96)
"""
from __future__ import annotations

from kink import inject

from main.app.config.settings import settings
from main.appodus_utils.integrations.kyc.interface import IKycProvider
from main.appodus_utils.integrations.kyc.models import (
    BvnVerificationRequest,
    GovIdVerificationRequest,
    KycMethod,
    KycProvider,
    KycResultStatus,
    KycVerificationResult,
)

# Sentinel identity numbers that drive each deterministic branch.
TEST_ID_FAILED = "00000000000"
TEST_ID_REVIEW = "11111111111"

_FAILED_SCORE = 10
_REVIEW_SCORE = 50
_VERIFIED_SCORE = 96


def _resolve(id_number: str) -> tuple[KycResultStatus, int]:
    if id_number == TEST_ID_FAILED:
        return KycResultStatus.FAILED, _FAILED_SCORE
    if id_number == TEST_ID_REVIEW:
        return KycResultStatus.NEEDS_REVIEW, _REVIEW_SCORE
    score = _VERIFIED_SCORE
    # Honour the configured threshold so the stub and the real provider apply the
    # same review gate.
    if score < settings.KYC_SELFIE_REVIEW_THRESHOLD:
        return KycResultStatus.NEEDS_REVIEW, score
    return KycResultStatus.VERIFIED, score


@inject
class StubKycProvider(IKycProvider):
    @property
    def platform(self) -> KycProvider:
        return KycProvider.STUB

    async def verify_bvn(self, payload: BvnVerificationRequest) -> KycVerificationResult:
        status, score = _resolve(payload.bvn)
        return KycVerificationResult(
            provider=KycProvider.STUB,
            method=KycMethod.BVN,
            status=status,
            provider_ref=f"STUB-BVN-{payload.bvn}",
            score=score,
            matched=status != KycResultStatus.FAILED,
            summary=f"stub bvn verification: {status.value}",
        )

    async def verify_id_document(self, payload: GovIdVerificationRequest) -> KycVerificationResult:
        status, score = _resolve(payload.id_number)
        return KycVerificationResult(
            provider=KycProvider.STUB,
            method=KycMethod.GOV_ID,
            status=status,
            provider_ref=f"STUB-{payload.id_type.value}-{payload.id_number}",
            score=score,
            matched=status != KycResultStatus.FAILED,
            summary=f"stub {payload.id_type.value} verification: {status.value}",
        )

    async def get_status(self, provider_ref: str) -> KycVerificationResult:
        # Deterministic replay: recover the id number encoded in the reference.
        id_number = provider_ref.rsplit("-", 1)[-1]
        status, score = _resolve(id_number)
        method = KycMethod.BVN if "-BVN-" in provider_ref else KycMethod.GOV_ID
        return KycVerificationResult(
            provider=KycProvider.STUB,
            method=method,
            status=status,
            provider_ref=provider_ref,
            score=score,
            matched=status != KycResultStatus.FAILED,
            summary=f"stub status: {status.value}",
        )
