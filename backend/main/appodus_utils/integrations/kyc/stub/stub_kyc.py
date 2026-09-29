"""Deterministic KYC stub — the default provider in local/test/dev.

Mirrors the OTP_MODE determinism contract: identity checks resolve to a fixed, predictable
outcome so autonomous QA (Playwright + Claude Code) is reproducible. Never hits a network.
Selected whenever ``settings.KYC_PROVIDER == STUB``.

It follows the live provider's rules, so the flows above it are the ones production runs:
liveness first, BVN and NIN resolved automatically, any other government ID sent to a
person. The outcome is keyed on the id number so tests can drive each branch:

- ``TEST_ID_NOT_LIVE`` → FAILED at liveness (for any method)
- ``TEST_ID_FAILED``   → FAILED (score 10)
- ``TEST_ID_REVIEW``   → NEEDS_REVIEW (score below the review threshold)
- passport / driver's licence / voter's card → NEEDS_REVIEW
- anything else        → VERIFIED (score 96)
"""
from __future__ import annotations

from kink import inject

from main.app.config.settings import settings
from main.appodus_utils.integrations.kyc.interface import IKycProvider
from main.appodus_utils.integrations.kyc.models import (
    AUTO_VERIFIABLE_ID_TYPES,
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
TEST_ID_NOT_LIVE = "33333333333"

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


def _result(method: KycMethod, ref: str, status: KycResultStatus, score, summary: str) -> KycVerificationResult:
    return KycVerificationResult(
        provider=KycProvider.STUB, method=method, status=status, provider_ref=ref, score=score,
        matched=None if score is None else status != KycResultStatus.FAILED, summary=summary,
    )


@inject
class StubKycProvider(IKycProvider):
    @property
    def platform(self) -> KycProvider:
        return KycProvider.STUB

    async def verify_bvn(self, payload: BvnVerificationRequest) -> KycVerificationResult:
        ref = f"STUB-BVN-{payload.bvn}"
        if payload.bvn == TEST_ID_NOT_LIVE:
            return _result(KycMethod.BVN, ref, KycResultStatus.FAILED, None, "stub: the selfie failed the liveness check")
        status, score = _resolve(payload.bvn)
        return _result(KycMethod.BVN, ref, status, score, f"stub bvn verification: {status.value}")

    async def verify_id_document(self, payload: GovIdVerificationRequest) -> KycVerificationResult:
        ref = f"STUB-{payload.id_type.value}-{payload.id_number}"
        if payload.id_number == TEST_ID_NOT_LIVE:
            return _result(KycMethod.GOV_ID, ref, KycResultStatus.FAILED, None, "stub: the selfie failed the liveness check")
        if payload.id_type not in AUTO_VERIFIABLE_ID_TYPES:
            return _result(KycMethod.GOV_ID, ref, KycResultStatus.NEEDS_REVIEW, None,
                           f"stub: {payload.id_type.value} is checked by a reviewer")
        status, score = _resolve(payload.id_number)
        return _result(KycMethod.GOV_ID, ref, status, score, f"stub {payload.id_type.value} verification: {status.value}")
