"""KYC provider facade DTOs (PRD §3.1).

Liveness and face-match are performed entirely by the third-party provider
(Dojah default). The platform persists the provider's *result* and *reference*
only — never raw biometric payloads. These DTOs are the provider-agnostic
contract the agent domain speaks to.
"""
from __future__ import annotations

import enum
from typing import Optional

from main.appodus_utils import Object


class KycProvider(str, enum.Enum):
    """Selectable KYC backend (settings.KYC_PROVIDER)."""

    STUB = "STUB"
    DOJAH = "DOJAH"


class KycMethod(str, enum.Enum):
    """How identity was asserted (PRD §3.1: BVN primary, gov-ID fallback)."""

    BVN = "BVN"
    GOV_ID = "GOV_ID"


class GovIdType(str, enum.Enum):
    NIN = "NIN"
    PASSPORT = "PASSPORT"
    DRIVERS_LICENCE = "DRIVERS_LICENCE"
    VOTERS_CARD = "VOTERS_CARD"


class KycResultStatus(str, enum.Enum):
    """Outcome of a provider verification call."""

    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    # Provider succeeded but the match score is below the review threshold
    # (settings.KYC_SELFIE_REVIEW_THRESHOLD) — routed to admin review.
    NEEDS_REVIEW = "NEEDS_REVIEW"
    PENDING = "PENDING"


class BvnVerificationRequest(Object):
    bvn: str
    first_name: str
    last_name: str
    # Provider performs liveness + face-match against this selfie reference; the
    # image itself is uploaded out-of-band and only the storage reference is
    # passed here so no raw biometric transits the domain layer.
    selfie_reference: Optional[str] = None


class GovIdVerificationRequest(Object):
    id_type: GovIdType
    id_number: str
    first_name: str
    last_name: str
    selfie_reference: Optional[str] = None


class KycVerificationResult(Object):
    """Provider-agnostic verification outcome persisted on the agent's KYC record.

    Contains no biometric data — only the provider's decision, reference, and a
    non-biometric summary safe to retain.
    """

    provider: KycProvider
    method: KycMethod
    status: KycResultStatus
    # Opaque provider transaction/verification id used for later status lookups.
    provider_ref: str
    # Face-match / liveness confidence when the provider returns one (0–100).
    score: Optional[int] = None
    matched: Optional[bool] = None
    # Human-readable provider message (never raw biometrics).
    summary: Optional[str] = None
