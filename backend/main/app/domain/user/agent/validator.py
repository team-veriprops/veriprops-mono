"""Agent application input + business-rule validation."""
from __future__ import annotations

from typing import List, Optional

from kink import inject

from main.app.domain.user.agent.models import (
    AgentApplication,
    AgentApplicationStatus,
    AgentType,
    CredentialsStepDto,
)
from main.appodus_utils.exception.exceptions import (
    InvalidResourceStateException,
    ValidationException,
)


# 36 Nigerian states + FCT.
NIGERIAN_STATES: set[str] = {
    "ABIA", "ADAMAWA", "AKWA_IBOM", "ANAMBRA", "BAUCHI", "BAYELSA", "BENUE",
    "BORNO", "CROSS_RIVER", "DELTA", "EBONYI", "EDO", "EKITI", "ENUGU", "FCT",
    "GOMBE", "IMO", "JIGAWA", "KADUNA", "KANO", "KATSINA", "KEBBI", "KOGI",
    "KWARA", "LAGOS", "NASARAWA", "NIGER", "OGUN", "ONDO", "OSUN", "OYO",
    "PLATEAU", "RIVERS", "SOKOTO", "TARABA", "YOBE", "ZAMFARA",
}


@inject
class AgentApplicationValidator:

    @staticmethod
    def assert_mutable(application: AgentApplication) -> None:
        if application.status not in (AgentApplicationStatus.DRAFT.value,):
            raise InvalidResourceStateException(
                resource="AgentApplication",
                message="Application can no longer be edited",
            )

    @staticmethod
    def assert_pending(application: AgentApplication) -> None:
        if application.status != AgentApplicationStatus.PENDING.value:
            raise InvalidResourceStateException(
                resource="AgentApplication",
                message="Only pending applications can be reviewed",
            )

    @staticmethod
    def assert_types(types: List[AgentType]) -> None:
        if not types:
            raise ValidationException(message="At least one agent type is required")
        seen: set[str] = set()
        for t in types:
            if t.value in seen:
                raise ValidationException(message=f"Duplicate agent type: {t.value}")
            seen.add(t.value)

    @staticmethod
    def assert_bvn(bvn: str) -> None:
        digits = (bvn or "").strip()
        if len(digits) != 11 or not digits.isdigit():
            raise ValidationException(message="BVN must be 11 digits")

    @staticmethod
    def assert_credentials(types: List[str], dto: CredentialsStepDto) -> None:
        upper = {t.upper() for t in (types or [])}
        if AgentType.SURVEYOR.value in upper:
            if not dto.surveyor_licence_no or not dto.surveyor_licence_url:
                raise ValidationException(
                    message="Surveyor licence number and document are required for the Surveyor role",
                )
        if AgentType.LAWYER.value in upper:
            if not dto.nba_licence_no or not dto.nba_licence_url:
                raise ValidationException(
                    message="NBA licence number and document are required for the Lawyer role",
                )
        if dto.bio is not None and len(dto.bio) > 300:
            raise ValidationException(message="Bio must not exceed 300 characters")
        if dto.years_of_experience is not None and (
            dto.years_of_experience < 0 or dto.years_of_experience > 80
        ):
            raise ValidationException(message="Years of experience is out of range")
        if not dto.coverage_states:
            raise ValidationException(message="At least one coverage state is required")
        invalid = [s for s in dto.coverage_states if s.upper() not in NIGERIAN_STATES]
        if invalid:
            raise ValidationException(message=f"Unknown Nigerian state(s): {', '.join(invalid)}")

    @staticmethod
    def assert_submission_ready(application: AgentApplication) -> None:
        if not application.types:
            raise ValidationException(message="Pick at least one agent type before submitting")
        if not application.kyc_method:
            raise ValidationException(message="Complete the KYC step before submitting")
        if application.kyc_method == "BVN" and not application.bvn_verification_id:
            raise ValidationException(message="BVN must be verified before submitting")
        if application.kyc_method == "ID_DOC" and (
            not application.id_doc_url or not application.selfie_url
        ):
            raise ValidationException(message="ID document and selfie are required before submitting")
        if not application.coverage_states:
            raise ValidationException(message="At least one coverage state is required")

    @staticmethod
    def assert_rejection_reason(reason: Optional[str]) -> None:
        if not reason or len(reason.strip()) < 30:
            raise ValidationException(message="Rejection reason must be at least 30 characters")
