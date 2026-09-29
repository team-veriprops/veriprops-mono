"""Dojah KYC provider (PRD §3.1 — the live provider, behind the facade).

Selected when ``settings.KYC_PROVIDER == DOJAH``; ``DOJAH_BASE_URL`` picks sandbox or
production (same API, different host). Instantiation is credential-free so bootstrap can
register every provider; credentials are checked on the first real call.

Every check is two calls:

1. ``POST /api/v1/ml/liveness`` — the selfie must show exactly one real, live face. A photo
   of a photo stops here, before any identity lookup is paid for.
2. For BVN and NIN, ``POST /api/v1/kyc/{bvn,nin}/verify`` matches the selfie to the photo
   on file and returns the record. The score decides — at or above
   ``KYC_SELFIE_REVIEW_THRESHOLD`` verifies, down to Dojah's floor (50) goes to a person,
   below it fails — and a record in another name also goes to a person.

Passport, driver's licence and voter's card have no photo-on-file match, so a live selfie
sends them to a reviewer, who compares it with the document photo.

Dojah's own messages are logged, never returned: the summary is always a sentence of ours.
"""
from __future__ import annotations

import re
import secrets
from typing import TYPE_CHECKING, Any, Dict, Iterable, Optional, Tuple

import httpx
from kink import di, inject

from main.app.config.settings import settings
from main.appodus_utils.config.settings import is_configured_secret
from main.appodus_utils.integrations.exception.exceptions import IntegrationException
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

if TYPE_CHECKING:
    from loguru import Logger

logger: Logger = di["logger"]

# Dojah's lowest accepted match threshold. Sent with every match so a weak score still comes
# back scored; the review band above it is ours to apply.
_DOJAH_MATCH_FLOOR = 50
# "No record for that number" — the applicant's failure, not an outage: a 404, or a 400 whose
# error says so. Any other 400 is a request we got wrong (an image Dojah rejects), an outage.
_NOT_FOUND_STATUS = 404
_NOT_FOUND_PHRASE = "not found"

_NOT_LIVE = "The selfie did not pass the liveness check. Retake it facing the camera in good light."
_NO_FACE = "The selfie must show exactly one face."
_NO_RECORD_SUMMARY = "No identity record matches that number."
_WEAK_MATCH = "The selfie is a weak match for the photo on file, so a reviewer will check it."
_NO_MATCH = "The selfie does not match the photo on file."
_NAME_MISMATCH = "The name on the identity record differs from the account name, so a reviewer will check it."
_MATCHED = "The selfie matches the photo on file."


class _NoRecord(Exception):
    """Dojah has no identity record for the number."""


@inject
class DojahKycProvider(IKycProvider):
    @property
    def platform(self) -> KycProvider:
        return KycProvider.DOJAH

    async def verify_bvn(self, payload: BvnVerificationRequest) -> KycVerificationResult:
        ref = _reference(KycMethod.BVN)
        selfie = payload.selfie_image.get_secret_value()
        refusal = await self._liveness(selfie)
        if refusal:
            return _result(KycMethod.BVN, ref, KycResultStatus.FAILED, None, refusal)
        try:
            entity = await self._post("/api/v1/kyc/bvn/verify", {
                "bvn": payload.bvn, "selfie_image": selfie, "threshold": _DOJAH_MATCH_FLOOR,
            }, "verify the BVN")
        except _NoRecord:
            return _result(KycMethod.BVN, ref, KycResultStatus.FAILED, None, _NO_RECORD_SUMMARY)
        return _decide(KycMethod.BVN, ref, entity, _record_names(entity), payload.first_name, payload.last_name)

    async def verify_id_document(self, payload: GovIdVerificationRequest) -> KycVerificationResult:
        ref = _reference(KycMethod.GOV_ID)
        selfie = payload.selfie_image.get_secret_value()
        refusal = await self._liveness(selfie)
        if refusal:
            return _result(KycMethod.GOV_ID, ref, KycResultStatus.FAILED, None, refusal)
        if payload.id_type not in AUTO_VERIFIABLE_ID_TYPES:
            return _result(KycMethod.GOV_ID, ref, KycResultStatus.NEEDS_REVIEW, None,
                           "The selfie is live; a reviewer will compare it with the ID document.")
        try:
            entity = await self._post("/api/v1/kyc/nin/verify", {
                "nin": payload.id_number, "selfie_image": selfie, "threshold": _DOJAH_MATCH_FLOOR,
                "first_name": payload.first_name, "last_name": payload.last_name,
            }, "verify the NIN")
        except _NoRecord:
            return _result(KycMethod.GOV_ID, ref, KycResultStatus.FAILED, None, _NO_RECORD_SUMMARY)
        return _decide(KycMethod.GOV_ID, ref, entity, _record_names(entity), payload.first_name, payload.last_name)

    # ── HTTP ─────────────────────────────────────────────────────

    async def _liveness(self, selfie: str) -> Optional[str]:
        """Why the selfie is refused, or ``None`` when it shows one live face."""
        try:
            entity = await self._post("/api/v1/ml/liveness", {"image": selfie}, "check the selfie")
        except _NoRecord:
            return _NO_FACE
        face = entity.get("face") or {}
        if not face.get("face_detected") or face.get("multiface_detected"):
            return _NO_FACE
        if not (entity.get("liveness") or {}).get("liveness_check"):
            return _NOT_LIVE
        return None

    async def _post(self, path: str, body: Dict[str, Any], action: str) -> Dict[str, Any]:
        if not (is_configured_secret(settings.DOJAH_APP_ID) and is_configured_secret(settings.DOJAH_PRIVATE_KEY)):
            logger.error("Dojah is the KYC provider but DOJAH_APP_ID / DOJAH_PRIVATE_KEY are not configured")
            raise IntegrationException("Could not verify your identity: the identity service is not available.")
        client: httpx.AsyncClient = di[httpx.AsyncClient]
        try:
            response = await client.post(
                f"{settings.DOJAH_BASE_URL.rstrip('/')}{path}", json=body,
                headers={
                    # The secret key as-is: Dojah rejects a Bearer prefix.
                    "Authorization": settings.DOJAH_PRIVATE_KEY, "AppId": settings.DOJAH_APP_ID,
                    "Content-Type": "application/json", "Accept": "application/json",
                },
            )
        except httpx.HTTPError as e:
            logger.error(f"Dojah unreachable while trying to {action}: {e!r}")
            raise IntegrationException("Could not verify your identity: the identity service is unreachable.") from e
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        error = str(payload.get("error") or "")
        if response.status_code == _NOT_FOUND_STATUS or (
            response.status_code == 400 and _NOT_FOUND_PHRASE in error.lower()
        ):
            logger.info(f"Dojah has no record to {action}: HTTP {response.status_code} {error!r}")
            raise _NoRecord()
        if response.is_error or "entity" not in payload:
            logger.error(f"Dojah refused to {action}: HTTP {response.status_code} {payload.get('error')!r}")
            raise IntegrationException("Could not verify your identity: the identity service is not available.")
        return payload["entity"] or {}


def _reference(method: KycMethod) -> str:
    """A random reference for the check. Never derived from the identity number: an 11-digit
    number hashed without a secret is recovered by brute force."""
    return f"DOJAH-{method.value}-{secrets.token_hex(12)}"


def _record_names(entity: Dict[str, Any]) -> Tuple[Optional[str], ...]:
    """The holder's names, under either naming Dojah uses (``first_name`` on the selfie
    endpoints, ``firstname``/``surname`` on the NIN lookups)."""
    return (
        entity.get("first_name") or entity.get("firstname"),
        entity.get("middle_name") or entity.get("middlename"),
        entity.get("last_name") or entity.get("surname"),
    )


def _tokens(names: Iterable[Optional[str]]) -> set:
    return {t for n in names if n for t in re.split(r"[^A-Z]+", n.upper()) if t}


def _names_match(record_names: Tuple[Optional[str], ...], first_name: str, last_name: str) -> bool:
    """The applicant's first and last names both appear on the record, in any order or case
    (records often swap them or fold the middle name in)."""
    record, wanted = _tokens(record_names), _tokens((first_name, last_name))
    return bool(wanted) and wanted <= record


def _decide(method: KycMethod, ref: str, entity: Dict[str, Any], record_names, first_name: str, last_name: str
            ) -> KycVerificationResult:
    confidence = float((entity.get("selfie_verification") or {}).get("confidence_value") or 0)
    score = round(confidence)
    if confidence < _DOJAH_MATCH_FLOOR:
        return _result(method, ref, KycResultStatus.FAILED, score, _NO_MATCH, matched=False)
    if confidence < settings.KYC_SELFIE_REVIEW_THRESHOLD:
        return _result(method, ref, KycResultStatus.NEEDS_REVIEW, score, _WEAK_MATCH, matched=True)
    if not _names_match(record_names, first_name, last_name):
        return _result(method, ref, KycResultStatus.NEEDS_REVIEW, score, _NAME_MISMATCH, matched=True)
    return _result(method, ref, KycResultStatus.VERIFIED, score, _MATCHED, matched=True)


def _result(method: KycMethod, ref: str, status: KycResultStatus, score: Optional[int], summary: str,
            matched: Optional[bool] = None) -> KycVerificationResult:
    return KycVerificationResult(
        provider=KycProvider.DOJAH, method=method, status=status, provider_ref=ref,
        score=score, matched=matched, summary=summary,
    )
