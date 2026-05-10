"""Dojah KYC webhook utilities.

validate_dojah_signature: HMAC-SHA256 guard — call before processing payload.
parse_dojah_selfie_webhook: extracts the correlation key (provider_ref), status,
  and selfie confidence score from Dojah's callback JSON.
"""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Optional


@dataclass
class DojahWebhookResult:
    provider_ref: str
    status: str        # "success" | "failed" | "pending"
    score: Optional[int]
    failure_reason: Optional[str]


def validate_dojah_signature(body: bytes, received_sig: str, secret: str) -> bool:
    """Return True iff the HMAC-SHA256 of body with secret matches received_sig."""
    if not secret or not received_sig:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received_sig)


def parse_dojah_selfie_webhook(payload: dict) -> DojahWebhookResult:
    """Parse Dojah's selfie-verification webhook payload.

    Dojah wraps results under ``entity``::

        {
          "entity": {
            "verification_id": "...",
            "status": "success" | "failed",
            "confidence_score": 91,
            "message": "..."
          }
        }
    """
    entity = payload.get("entity") or {}
    provider_ref = (
        entity.get("verification_id")
        or payload.get("verification_id")
        or ""
    )
    status = (entity.get("status") or payload.get("status") or "failed").lower()
    raw_score = entity.get("confidence_score") or entity.get("score")
    score: Optional[int] = int(raw_score) if raw_score is not None else None
    failure_reason: Optional[str] = None
    if status != "success":
        failure_reason = entity.get("message") or payload.get("message") or "Selfie verification failed"

    return DojahWebhookResult(
        provider_ref=str(provider_ref),
        status=status,
        score=score,
        failure_reason=failure_reason,
    )
