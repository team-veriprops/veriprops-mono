"""KYC orchestration for agent onboarding (PRD §3.1).

Wraps the provider facade: runs the verification through the active provider and
persists the *result* (never raw biometrics) as a KycRecord. BVN is primary;
government-ID is the fallback.
"""
from __future__ import annotations

from typing import Optional

from kink import inject

from main.app.domain.user.agent.models import (
    CreateKycRecordDto,
    KycRecord,
    KycSubmissionDto,
)
from main.app.domain.user.agent.repo import KycRecordRepo
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import ValidationException
from main.appodus_utils.integrations.kyc.factory import KycProviderFactory
from main.appodus_utils.integrations.kyc.models import (
    BvnVerificationRequest,
    GovIdVerificationRequest,
    KycMethod,
    KycResultStatus,
    KycVerificationResult,
)


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class KycService:
    def __init__(self, kyc_factory: KycProviderFactory, kyc_repo: KycRecordRepo):
        self._kyc_factory = kyc_factory
        self._kyc_repo = kyc_repo

    async def run_verification(
        self, user_id: str, first_name: str, last_name: str, submission: KycSubmissionDto
    ) -> KycRecord:
        provider = self._kyc_factory.get_active_provider()
        result = await self._verify(provider, first_name, last_name, submission)

        verified_at = (
            Utils.datetime_now() if result.status == KycResultStatus.VERIFIED else None
        )
        return await self._kyc_repo.create_return_model(CreateKycRecordDto(
            user_id=user_id,
            provider=result.provider,
            method=result.method,
            status=result.status,
            provider_ref=result.provider_ref,
            score=result.score,
            summary=result.summary,
            verified_at=verified_at,
        ))

    async def _verify(
        self, provider, first_name: str, last_name: str, submission: KycSubmissionDto
    ) -> KycVerificationResult:
        if submission.method == KycMethod.BVN:
            if not submission.bvn:
                raise ValidationException(message="BVN is required for BVN verification.")
            return await provider.verify_bvn(BvnVerificationRequest(
                bvn=submission.bvn,
                first_name=first_name,
                last_name=last_name,
                selfie_reference=submission.selfie_reference,
            ))
        if not submission.id_type or not submission.id_number:
            raise ValidationException(message="ID type and number are required for ID verification.")
        return await provider.verify_id_document(GovIdVerificationRequest(
            id_type=submission.id_type,
            id_number=submission.id_number,
            first_name=first_name,
            last_name=last_name,
            selfie_reference=submission.selfie_reference,
        ))

    async def get_latest(self, user_id: str) -> Optional[KycRecord]:
        return await self._kyc_repo.get_latest_for_user(user_id)
