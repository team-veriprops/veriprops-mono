"""Deterministic KYC stub (PRD §3.1) — every branch is reproducible for automation.

The stub is the default provider in test; it must never persist raw biometrics and
must resolve identity to a fixed outcome keyed on the id number.
"""
import pytest

from main.appodus_utils.integrations.kyc.factory import KycProviderFactory
from main.appodus_utils.integrations.kyc.models import (
    BvnVerificationRequest,
    GovIdType,
    GovIdVerificationRequest,
    KycMethod,
    KycProvider,
    KycResultStatus,
)
from main.appodus_utils.integrations.kyc.stub.stub_kyc import (
    TEST_ID_FAILED,
    TEST_ID_REVIEW,
    StubKycProvider,
)


@pytest.fixture
def provider() -> StubKycProvider:
    return StubKycProvider()


class TestStubBvn:
    async def test_valid_bvn_verifies(self, provider):
        result = await provider.verify_bvn(
            BvnVerificationRequest(bvn="22222222222", first_name="Ada", last_name="Obi")
        )
        assert result.status == KycResultStatus.VERIFIED
        assert result.provider == KycProvider.STUB
        assert result.method == KycMethod.BVN
        assert result.matched is True
        assert result.score >= 80
        assert result.provider_ref == "STUB-BVN-22222222222"

    async def test_sentinel_bvn_fails(self, provider):
        result = await provider.verify_bvn(
            BvnVerificationRequest(bvn=TEST_ID_FAILED, first_name="Ada", last_name="Obi")
        )
        assert result.status == KycResultStatus.FAILED
        assert result.matched is False

    async def test_sentinel_bvn_needs_review(self, provider):
        result = await provider.verify_bvn(
            BvnVerificationRequest(bvn=TEST_ID_REVIEW, first_name="Ada", last_name="Obi")
        )
        assert result.status == KycResultStatus.NEEDS_REVIEW

    async def test_result_carries_no_biometrics(self, provider):
        """The persisted result must be free of image/biometric payloads."""
        result = await provider.verify_bvn(
            BvnVerificationRequest(
                bvn="22222222222", first_name="Ada", last_name="Obi", selfie_reference="s3://ref"
            )
        )
        dumped = result.model_dump()
        assert "selfie" not in dumped and "image" not in dumped and "biometric" not in dumped


class TestStubGovId:
    async def test_valid_gov_id_verifies(self, provider):
        result = await provider.verify_id_document(
            GovIdVerificationRequest(
                id_type=GovIdType.NIN, id_number="55555555555", first_name="Ada", last_name="Obi"
            )
        )
        assert result.status == KycResultStatus.VERIFIED
        assert result.method == KycMethod.GOV_ID
        assert result.provider_ref == "STUB-NIN-55555555555"


class TestStubStatusReplay:
    async def test_get_status_is_deterministic(self, provider):
        first = await provider.verify_bvn(
            BvnVerificationRequest(bvn="22222222222", first_name="Ada", last_name="Obi")
        )
        replay = await provider.get_status(first.provider_ref)
        assert replay.status == first.status
        assert replay.method == KycMethod.BVN


class TestFactory:
    def test_default_active_provider_is_stub(self):
        # ENVIRONMENT=test → KYC_PROVIDER defaults to STUB.
        factory = KycProviderFactory([StubKycProvider()])
        assert isinstance(factory.get_active_provider(), StubKycProvider)
        assert factory.get_provider(KycProvider.STUB).platform == KycProvider.STUB
