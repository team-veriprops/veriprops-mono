"""Deterministic KYC stub (PRD §3.1) — every branch is reproducible for automation.

The stub is the default provider in test. It follows the live provider's rules — a selfie
must pass liveness first, BVN and NIN resolve automatically, other government IDs go to a
person — with each outcome keyed on the id number, so tests can drive every branch.
"""
import pytest
from pydantic import SecretStr

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
    TEST_ID_NOT_LIVE,
    TEST_ID_REVIEW,
    StubKycProvider,
)

SELFIE = SecretStr("/9j/4AAQSkZJRgABAQ")


def _bvn(bvn="22222222222"):
    return BvnVerificationRequest(bvn=bvn, first_name="Ada", last_name="Obi", selfie_image=SELFIE)


def _gov(id_type=GovIdType.NIN, number="55555555555"):
    return GovIdVerificationRequest(
        id_type=id_type, id_number=number, first_name="Ada", last_name="Obi", selfie_image=SELFIE,
    )


@pytest.fixture
def provider() -> StubKycProvider:
    return StubKycProvider()


class TestStubBvn:
    async def test_valid_bvn_verifies(self, provider):
        result = await provider.verify_bvn(_bvn())
        assert result.status == KycResultStatus.VERIFIED
        assert result.provider == KycProvider.STUB
        assert result.method == KycMethod.BVN
        assert result.matched is True
        assert result.score >= 80
        assert result.provider_ref == "STUB-BVN-22222222222"

    async def test_sentinel_bvn_fails(self, provider):
        result = await provider.verify_bvn(_bvn(TEST_ID_FAILED))
        assert result.status == KycResultStatus.FAILED
        assert result.matched is False

    async def test_sentinel_bvn_needs_review(self, provider):
        assert (await provider.verify_bvn(_bvn(TEST_ID_REVIEW))).status == KycResultStatus.NEEDS_REVIEW

    async def test_a_selfie_that_is_not_live_fails_whatever_the_number(self, provider):
        result = await provider.verify_bvn(_bvn(TEST_ID_NOT_LIVE))
        assert result.status == KycResultStatus.FAILED
        assert "liveness" in result.summary.lower()

    async def test_result_carries_no_biometrics(self, provider):
        """The result persisted on the KYC record is free of image payloads."""
        dumped = (await provider.verify_bvn(_bvn())).model_dump()
        assert "selfie" not in dumped and "image" not in dumped and "biometric" not in dumped


class TestStubGovId:
    async def test_a_nin_verifies_automatically(self, provider):
        result = await provider.verify_id_document(_gov())
        assert result.status == KycResultStatus.VERIFIED
        assert result.method == KycMethod.GOV_ID
        assert result.provider_ref == "STUB-NIN-55555555555"

    @pytest.mark.parametrize("id_type", [GovIdType.PASSPORT, GovIdType.DRIVERS_LICENCE, GovIdType.VOTERS_CARD])
    async def test_other_ids_go_to_a_person(self, provider, id_type):
        # As with Dojah: only BVN and NIN can be matched to a photo on file.
        assert (await provider.verify_id_document(_gov(id_type, "A01234567"))).status == KycResultStatus.NEEDS_REVIEW

    async def test_other_ids_with_a_selfie_that_is_not_live_fail(self, provider):
        result = await provider.verify_id_document(_gov(GovIdType.PASSPORT, TEST_ID_NOT_LIVE))
        assert result.status == KycResultStatus.FAILED


class TestFactory:
    def test_default_active_provider_is_stub(self):
        # ENVIRONMENT=test → KYC_PROVIDER defaults to STUB.
        factory = KycProviderFactory([StubKycProvider()])
        assert isinstance(factory.get_active_provider(), StubKycProvider)
        assert factory.get_provider(KycProvider.STUB).platform == KycProvider.STUB
