"""Validation logic tests for signup payloads."""
import pytest

from main.app.domain.user.auth.models import SignupRequestDto, UserConsentInputDto
from main.app.domain.user.auth.consent.models import ConsentDocumentType
from main.appodus_utils import Utils


def _valid_payload() -> dict:
    return {
        "first_name": "Adaeze",
        "last_name": "Williams",
        "email": "ada@example.com",
        "password": "Sup3rSecure!Pwd",
        "country_code": "NG",
        "dial_code": "+234",
        "phone": "8012345678",
        "country_of_residence": "NG",
        "timezone": "Africa/Lagos",
        "preferred_currency": "NGN",
        "consents": [
            {
                "document_type": ConsentDocumentType.PLATFORM_TERMS.value,
                "consent_version": "1.0.0",
                "accepted_at": Utils.datetime_now().isoformat(),
            },
            {
                "document_type": ConsentDocumentType.PRIVACY_POLICY.value,
                "consent_version": "1.0.0",
                "accepted_at": Utils.datetime_now().isoformat(),
            },
        ],
    }


class TestSignupRequestDto:
    def test_accepts_valid_payload(self):
        dto = SignupRequestDto.model_validate(_valid_payload())
        assert dto.email == "ada@example.com"
        assert len(dto.consents) == 2

    def test_rejects_invalid_email(self):
        payload = _valid_payload()
        payload["email"] = "not-an-email"
        with pytest.raises(Exception):
            SignupRequestDto.model_validate(payload)

    def test_camel_case_alias_accepted(self):
        payload = {
            "firstName": "Ada",
            "lastName": "W",
            "email": "ada@example.com",
            "password": "Sup3rSecure!Pwd",
            "countryCode": "NG",
            "dialCode": "+234",
            "phone": "8012345678",
            "countryOfResidence": "NG",
            "timezone": "Africa/Lagos",
            "preferredCurrency": "NGN",
            "consents": [],
        }
        dto = SignupRequestDto.model_validate(payload)
        assert dto.first_name == "Ada"
        assert dto.country_code == "NG"


class TestUserConsentInputDto:
    def test_round_trip(self):
        dto = UserConsentInputDto.model_validate({
            "documentType": ConsentDocumentType.PLATFORM_TERMS.value,
            "consentVersion": "1.0.0",
            "acceptedAt": Utils.datetime_now().isoformat(),
        })
        assert dto.document_type == ConsentDocumentType.PLATFORM_TERMS
        assert dto.consent_version == "1.0.0"
