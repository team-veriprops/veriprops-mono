"""Dojah KYC provider.

BVN verification is synchronous (GET /api/v1/kyc/bvn/advance).
Selfie submission is asynchronous — Dojah returns a verification_id
immediately, then POSTs a webhook when the liveness check is complete.
Use submit_selfie() to initiate; results arrive at the webhook endpoint.
"""
from __future__ import annotations

import base64
from typing import Optional

import httpx

from main.app.config.settings import settings
from main.app.domain.user.agent.kyc.interface import (
    BvnVerificationResult,
    KycProvider,
    SelfieMatchResult,
)
from main.appodus_utils.integrations.exception.exceptions import IntegrationException

_BASE = "https://api.dojah.io"
_TIMEOUT = 30.0


def _headers() -> dict:
    return {
        "AppId": settings.DOJAH_APP_ID,
        "Authorization": settings.DOJAH_PRIVATE_KEY,
        "Content-Type": "application/json",
    }


class DojahKycProvider(KycProvider):

    async def verify_bvn(self, bvn: str) -> BvnVerificationResult:
        url = f"{_BASE}/api/v1/kyc/bvn/advance"
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(url, params={"bvn": bvn}, headers=_headers())
            resp.raise_for_status()
        except httpx.TimeoutException as exc:
            raise IntegrationException(
                message="Dojah BVN verification timed out",
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise IntegrationException(
                message=f"Dojah BVN verification failed: HTTP {exc.response.status_code}",
            ) from exc

        body = resp.json()
        entity = body.get("entity") or {}
        verified = bool(entity.get("bvn") or entity.get("verified"))
        verification_id = entity.get("reference_id") or entity.get("id")
        failure_reason = None if verified else (body.get("error") or "BVN could not be verified")

        return BvnVerificationResult(
            verified=verified,
            verification_id=str(verification_id) if verification_id else None,
            failure_reason=failure_reason,
            provider="dojah",
        )

    async def match_selfie(
        self,
        selfie_bytes: bytes,
        reference_image_bytes: Optional[bytes] = None,
    ) -> SelfieMatchResult:
        # Dojah selfie verification is async-only in the S8 design.
        # Use submit_selfie() to initiate; result arrives via webhook.
        raise NotImplementedError(
            "Dojah selfie verification is async — use submit_selfie() "
            "and handle the result via the KYC webhook endpoint."
        )

    async def submit_selfie(
        self,
        selfie_bytes: bytes,
        reference_bvn_last4: Optional[str] = None,
    ) -> str:
        """POST selfie to Dojah; returns the verification_id used as webhook correlation key."""
        url = f"{_BASE}/api/v1/kyc/selfie"
        image_b64 = base64.b64encode(selfie_bytes).decode()
        payload: dict = {"selfie_image": image_b64}
        if reference_bvn_last4:
            payload["bvn_last4"] = reference_bvn_last4

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(url, json=payload, headers=_headers())
            resp.raise_for_status()
        except httpx.TimeoutException as exc:
            raise IntegrationException(
                message="Dojah selfie submission timed out",
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise IntegrationException(
                message=f"Dojah selfie submission failed: HTTP {exc.response.status_code}",
            ) from exc

        body = resp.json()
        entity = body.get("entity") or {}
        verification_id = entity.get("verification_id") or entity.get("id")
        if not verification_id:
            raise IntegrationException(
                message="Dojah selfie submission returned no verification_id",
            )
        return str(verification_id)
