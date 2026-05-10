"""Unit tests for KYC webhook utilities (S8 — R3.2).

Verifies:
- validate_dojah_signature: accepts valid HMAC, rejects tampered/missing sig
- parse_dojah_selfie_webhook: maps status/score to DojahWebhookResult correctly
"""
import hashlib
import hmac

from main.app.domain.user.agent.kyc.webhook import (
    DojahWebhookResult,
    parse_dojah_selfie_webhook,
    validate_dojah_signature,
)


_SECRET = "test-webhook-secret"


def _sign(body: bytes, secret: str = _SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


# ── Signature validation ──────────────────────────────────────────


def test_valid_signature_accepted():
    body = b'{"entity":{"verification_id":"abc"}}'
    sig = _sign(body)
    assert validate_dojah_signature(body, sig, _SECRET) is True


def test_tampered_body_rejected():
    body = b'{"entity":{"verification_id":"abc"}}'
    sig = _sign(body)
    tampered = b'{"entity":{"verification_id":"xyz"}}'
    assert validate_dojah_signature(tampered, sig, _SECRET) is False


def test_missing_secret_rejects():
    body = b'{"entity":{}}'
    sig = _sign(body)
    assert validate_dojah_signature(body, sig, "") is False


def test_missing_signature_rejects():
    body = b'{"entity":{}}'
    assert validate_dojah_signature(body, "", _SECRET) is False


# ── Webhook payload parsing ───────────────────────────────────────


def test_parse_success_high_score_maps_correctly():
    payload = {
        "entity": {
            "verification_id": "vf-001",
            "status": "success",
            "confidence_score": 92,
        }
    }
    result = parse_dojah_selfie_webhook(payload)
    assert result.provider_ref == "vf-001"
    assert result.status == "success"
    assert result.score == 92
    assert result.failure_reason is None


def test_parse_success_low_score_sets_no_failure_reason():
    payload = {
        "entity": {
            "verification_id": "vf-002",
            "status": "success",
            "confidence_score": 65,
        }
    }
    result = parse_dojah_selfie_webhook(payload)
    assert result.status == "success"
    assert result.score == 65
    assert result.failure_reason is None


def test_parse_failed_sets_failure_reason():
    payload = {
        "entity": {
            "verification_id": "vf-003",
            "status": "failed",
            "message": "Face could not be detected",
        }
    }
    result = parse_dojah_selfie_webhook(payload)
    assert result.status == "failed"
    assert result.failure_reason == "Face could not be detected"
    assert result.score is None


def test_parse_top_level_verification_id_fallback():
    """provider_ref falls back to top-level verification_id if entity is absent."""
    payload = {
        "verification_id": "vf-top",
        "status": "success",
        "confidence_score": 88,
    }
    result = parse_dojah_selfie_webhook(payload)
    assert result.provider_ref == "vf-top"
