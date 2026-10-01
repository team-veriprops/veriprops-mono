"""KYC provider facade DTOs (PRD §3.1).

Liveness and face-match are performed by the third-party provider (Dojah default). The
selfie travels to the provider as a `SecretStr`, so no log line that prints a request can
print a face; the provider's *result* carries no image at all. These DTOs are the
provider-agnostic contract the agent domain speaks to.
"""
from __future__ import annotations

import enum
from typing import Optional

from pydantic import SecretStr

from main.appodus_utils import Object
# Re-exported: the selector enum lives beside Settings, which cannot import this package.
from main.appodus_utils.config.providers import KycProvider  # noqa: F401


class KycMethod(str, enum.Enum):
    """How identity was asserted (PRD §3.1: BVN primary, gov-ID fallback)."""

    BVN = "BVN"
    GOV_ID = "GOV_ID"


class GovIdType(str, enum.Enum):
    NIN = "NIN"
    PASSPORT = "PASSPORT"
    DRIVERS_LICENCE = "DRIVERS_LICENCE"
    VOTERS_CARD = "VOTERS_CARD"


# The government IDs a provider can match against a photo on file. The others are checked by
# a person, from the selfie beside a photo of the document.
AUTO_VERIFIABLE_ID_TYPES = {GovIdType.NIN}


class KycResultStatus(str, enum.Enum):
    """Outcome of a provider verification call."""

    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    # A person decides: the selfie match is weak, the record's name is not the applicant's, or
    # the ID is one no provider can match automatically.
    NEEDS_REVIEW = "NEEDS_REVIEW"
    PENDING = "PENDING"


class BvnVerificationRequest(Object):
    bvn: str
    first_name: str
    last_name: str
    # Base64 JPEG, without a data-URL prefix.
    selfie_image: SecretStr


class GovIdVerificationRequest(Object):
    id_type: GovIdType
    id_number: str
    first_name: str
    last_name: str
    selfie_image: SecretStr


class KycVerificationResult(Object):
    """Provider-agnostic verification outcome persisted on the agent's KYC record.

    Contains no biometric data — only the provider's decision, reference, and a
    non-biometric summary safe to retain.
    """

    provider: KycProvider
    method: KycMethod
    status: KycResultStatus
    # Opaque reference for the check. Never the raw identity number for a live provider.
    provider_ref: str
    # Face-match confidence when the provider returns one (0–100).
    score: Optional[int] = None
    matched: Optional[bool] = None
    # A sentence of our own for the reviewer and the applicant (never the provider's text).
    summary: Optional[str] = None
