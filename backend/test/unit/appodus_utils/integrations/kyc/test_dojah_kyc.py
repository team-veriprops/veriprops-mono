"""Live Dojah KYC contract, pinned against Dojah's documented HTTP shapes.

CI and e2e never reach Dojah (KYC_PROVIDER=STUB), so these respx tests hold the adapter to
what Dojah accepts and to how its answers become one `KycVerificationResult`:

* every check starts with **liveness** on the selfie — a photo of a photo never reaches the
  identity match;
* BVN and NIN are matched against the photo on file (`/kyc/{bvn,nin}/verify`), and the name
  on the record must be the applicant's own;
* passport, driver's licence and voter's card cannot be matched automatically, so a live
  selfie sends them to a person (NEEDS_REVIEW);
* Dojah's own words never leave the adapter, and a Dojah that is down or unpaid is an
  integration failure — never an applicant who "failed" KYC.
"""
import json

import httpx
import pytest
import respx
from pydantic import SecretStr

from main.app.config.settings import settings
from main.appodus_utils.integrations.exception.exceptions import IntegrationException
from main.appodus_utils.integrations.kyc.dojah.dojah_kyc import DojahKycProvider
from main.appodus_utils.integrations.kyc.models import (
    BvnVerificationRequest,
    GovIdType,
    GovIdVerificationRequest,
    KycMethod,
    KycProvider,
    KycResultStatus,
)

DOJAH = "https://sandbox.dojah.test"
SELFIE = "/9j/4AAQSkZJRgABAQ"


@pytest.fixture(autouse=True)
def dojah_settings(monkeypatch):
    monkeypatch.setattr(settings, "DOJAH_BASE_URL", DOJAH)
    monkeypatch.setattr(settings, "DOJAH_APP_ID", "app-123")
    monkeypatch.setattr(settings, "DOJAH_PRIVATE_KEY", "test_sk_abc")
    monkeypatch.setattr(settings, "KYC_SELFIE_REVIEW_THRESHOLD", 80)


def _live(passed=True, faces=1):
    return httpx.Response(200, json={"entity": {
        "face": {"face_detected": faces > 0, "multiface_detected": faces > 1},
        "liveness": {"liveness_check": passed, "liveness_probability": 98 if passed else 12},
    }})


def _bvn_record(confidence=99.9, first="ADA", last="OBI", middle="NNEKA"):
    return httpx.Response(200, json={"entity": {
        "bvn": "2*****22222", "first_name": first, "middle_name": middle, "last_name": last,
        "selfie_verification": {"confidence_value": confidence, "match": confidence >= 50},
    }})


def _bvn(bvn="22222222222", first="Ada", last="Obi"):
    return BvnVerificationRequest(bvn=bvn, first_name=first, last_name=last, selfie_image=SecretStr(SELFIE))


def _gov(id_type=GovIdType.NIN, number="70123456789", first="John", last="Musa"):
    return GovIdVerificationRequest(
        id_type=id_type, id_number=number, first_name=first, last_name=last, selfie_image=SecretStr(SELFIE),
    )


class TestBvn:
    @respx.mock
    async def test_a_live_selfie_that_matches_the_bvn_photo_verifies(self):
        liveness = respx.post(f"{DOJAH}/api/v1/ml/liveness").mock(return_value=_live())
        verify = respx.post(f"{DOJAH}/api/v1/kyc/bvn/verify").mock(return_value=_bvn_record(99.9))

        result = await DojahKycProvider().verify_bvn(_bvn())

        assert (result.provider, result.method, result.status) == (
            KycProvider.DOJAH, KycMethod.BVN, KycResultStatus.VERIFIED,
        )
        assert (result.score, result.matched) == (100, True)
        # Authorization is the secret key as-is — Dojah rejects a Bearer prefix.
        headers = verify.calls.last.request.headers
        assert (headers["authorization"], headers["appid"]) == ("test_sk_abc", "app-123")
        assert json.loads(liveness.calls.last.request.content) == {"image": SELFIE}
        body = json.loads(verify.calls.last.request.content)
        # Dojah's floor, so a weak match comes back scored and the review band is ours to apply.
        assert body == {"bvn": "22222222222", "selfie_image": SELFIE, "threshold": 50}

    @respx.mock
    async def test_the_reference_reveals_nothing_about_the_bvn(self):
        # An 11-digit number hashed without a secret is recovered by brute force in hours, so
        # the reference is random: two checks of one BVN share nothing.
        respx.post(f"{DOJAH}/api/v1/ml/liveness").mock(return_value=_live())
        respx.post(f"{DOJAH}/api/v1/kyc/bvn/verify").mock(return_value=_bvn_record())

        first = await DojahKycProvider().verify_bvn(_bvn())
        second = await DojahKycProvider().verify_bvn(_bvn())

        assert "22222222222" not in first.provider_ref
        assert first.provider_ref != second.provider_ref

    @respx.mock
    async def test_a_selfie_that_is_not_live_fails_before_any_identity_lookup(self):
        respx.post(f"{DOJAH}/api/v1/ml/liveness").mock(return_value=_live(passed=False))
        verify = respx.post(f"{DOJAH}/api/v1/kyc/bvn/verify").mock(return_value=_bvn_record())

        result = await DojahKycProvider().verify_bvn(_bvn())

        assert result.status == KycResultStatus.FAILED
        assert "liveness" in result.summary.lower()
        assert not verify.called

    @pytest.mark.parametrize("faces", [0, 2])
    @respx.mock
    async def test_a_selfie_without_exactly_one_face_fails(self, faces):
        respx.post(f"{DOJAH}/api/v1/ml/liveness").mock(return_value=_live(faces=faces))

        result = await DojahKycProvider().verify_bvn(_bvn())

        assert result.status == KycResultStatus.FAILED

    @pytest.mark.parametrize("confidence, expected", [
        (80.0, KycResultStatus.VERIFIED),        # at the review threshold
        (79.4, KycResultStatus.NEEDS_REVIEW),    # a weak match goes to a person
        (50.0, KycResultStatus.NEEDS_REVIEW),
        (49.9, KycResultStatus.FAILED),          # below Dojah's floor
    ])
    @respx.mock
    async def test_the_match_score_decides_between_verified_review_and_failed(self, confidence, expected):
        respx.post(f"{DOJAH}/api/v1/ml/liveness").mock(return_value=_live())
        respx.post(f"{DOJAH}/api/v1/kyc/bvn/verify").mock(return_value=_bvn_record(confidence))

        assert (await DojahKycProvider().verify_bvn(_bvn())).status == expected

    @respx.mock
    async def test_a_record_in_someone_elses_name_goes_to_review(self):
        respx.post(f"{DOJAH}/api/v1/ml/liveness").mock(return_value=_live())
        respx.post(f"{DOJAH}/api/v1/kyc/bvn/verify").mock(return_value=_bvn_record(first="EMEKA", last="EZE"))

        result = await DojahKycProvider().verify_bvn(_bvn())

        assert result.status == KycResultStatus.NEEDS_REVIEW
        assert "name" in result.summary.lower()

    @respx.mock
    async def test_names_match_whatever_their_case_order_or_middle_name(self):
        respx.post(f"{DOJAH}/api/v1/ml/liveness").mock(return_value=_live())
        respx.post(f"{DOJAH}/api/v1/kyc/bvn/verify").mock(return_value=_bvn_record(first="OBI", last="ADA-NNEKA"))

        assert (await DojahKycProvider().verify_bvn(_bvn(first="ada", last="Obi"))).status == KycResultStatus.VERIFIED

    @pytest.mark.parametrize("status, error", [(404, "Not Found"), (400, "BVN not found")])
    @respx.mock
    async def test_a_number_dojah_has_no_record_of_fails_the_applicant(self, status, error):
        respx.post(f"{DOJAH}/api/v1/ml/liveness").mock(return_value=_live())
        respx.post(f"{DOJAH}/api/v1/kyc/bvn/verify").mock(return_value=httpx.Response(status, json={"error": error}))

        result = await DojahKycProvider().verify_bvn(_bvn())

        assert result.status == KycResultStatus.FAILED
        assert error not in result.summary

    @respx.mock
    async def test_any_other_bad_request_is_an_outage_not_a_failed_applicant(self):
        # A malformed image or body is our fault, not the applicant's.
        respx.post(f"{DOJAH}/api/v1/ml/liveness").mock(return_value=httpx.Response(400, json={
            "error": "Invalid image format",
        }))

        with pytest.raises(IntegrationException):
            await DojahKycProvider().verify_bvn(_bvn())

    @pytest.mark.parametrize("status", [401, 402, 429, 500, 503])
    @respx.mock
    async def test_a_dojah_that_cannot_serve_is_an_outage_not_a_failed_applicant(self, status):
        respx.post(f"{DOJAH}/api/v1/ml/liveness").mock(return_value=httpx.Response(status, json={
            "error": "Insufficient wallet balance",
        }))

        with pytest.raises(IntegrationException) as exc:
            await DojahKycProvider().verify_bvn(_bvn())
        assert "wallet" not in str(exc.value)

    @respx.mock
    async def test_an_unreachable_dojah_is_an_outage(self):
        respx.post(f"{DOJAH}/api/v1/ml/liveness").mock(side_effect=httpx.ConnectTimeout("timed out"))

        with pytest.raises(IntegrationException):
            await DojahKycProvider().verify_bvn(_bvn())

    async def test_unconfigured_credentials_are_an_outage(self, monkeypatch):
        monkeypatch.setattr(settings, "DOJAH_PRIVATE_KEY", "CHANGE_ME")

        with pytest.raises(IntegrationException):
            await DojahKycProvider().verify_bvn(_bvn())


class TestGovernmentId:
    @respx.mock
    async def test_a_nin_is_matched_against_its_photo_with_the_applicants_name(self):
        respx.post(f"{DOJAH}/api/v1/ml/liveness").mock(return_value=_live())
        verify = respx.post(f"{DOJAH}/api/v1/kyc/nin/verify").mock(return_value=httpx.Response(200, json={"entity": {
            "nin": "7*****83753", "firstname": "JOHN", "surname": "MUSA",
            "selfie_verification": {"confidence_value": 99.81, "match": True},
        }}))

        result = await DojahKycProvider().verify_id_document(_gov())

        assert (result.method, result.status) == (KycMethod.GOV_ID, KycResultStatus.VERIFIED)
        assert json.loads(verify.calls.last.request.content) == {
            "nin": "70123456789", "selfie_image": SELFIE, "threshold": 50,
            "first_name": "John", "last_name": "Musa",
        }

    @pytest.mark.parametrize("names", [
        {"firstname": "JOHN", "surname": "MUSA"},        # the NIN lookup's field names
        {"first_name": "JOHN", "last_name": "MUSA"},     # the selfie endpoint's documented ones
    ])
    @respx.mock
    async def test_the_nin_record_name_is_read_under_either_field_naming(self, names):
        respx.post(f"{DOJAH}/api/v1/ml/liveness").mock(return_value=_live())
        respx.post(f"{DOJAH}/api/v1/kyc/nin/verify").mock(return_value=httpx.Response(200, json={"entity": {
            **names, "selfie_verification": {"confidence_value": 99.0, "match": True},
        }}))

        assert (await DojahKycProvider().verify_id_document(_gov())).status == KycResultStatus.VERIFIED

    @pytest.mark.parametrize("id_type", [GovIdType.PASSPORT, GovIdType.DRIVERS_LICENCE, GovIdType.VOTERS_CARD])
    @respx.mock
    async def test_other_ids_go_to_a_person_once_the_selfie_is_live(self, id_type):
        respx.post(f"{DOJAH}/api/v1/ml/liveness").mock(return_value=_live())
        nin = respx.post(f"{DOJAH}/api/v1/kyc/nin/verify")

        result = await DojahKycProvider().verify_id_document(_gov(id_type=id_type, number="A01234567"))

        assert result.status == KycResultStatus.NEEDS_REVIEW
        assert not nin.called

    @respx.mock
    async def test_other_ids_with_a_selfie_that_is_not_live_fail(self):
        respx.post(f"{DOJAH}/api/v1/ml/liveness").mock(return_value=_live(passed=False))

        result = await DojahKycProvider().verify_id_document(_gov(id_type=GovIdType.PASSPORT, number="A01234567"))

        assert result.status == KycResultStatus.FAILED


class TestSelfieIsSecret:
    def test_a_request_never_prints_the_selfie(self):
        # The trace loggers log method arguments; a face must not end up in a log line.
        assert SELFIE not in repr(_bvn())
        assert SELFIE not in str(_gov())
