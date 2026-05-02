"""Verification input validators."""
from __future__ import annotations

from kink import inject

from main.app.domain.verification.models import (
    Verification,
    VerificationStatus,
)
from main.app.domain.verification.state_machine import verification_state_machine
from main.appodus_utils.exception.exceptions import ValidationException


@inject
class VerificationValidator:

    @staticmethod
    def assert_owner(verification: Verification, customer_id: str) -> None:
        if str(verification.customer_id) != customer_id:
            raise ValidationException(message="Verification not owned by current user")

    @staticmethod
    def assert_can_transition(current: str, target: str) -> None:
        verification_state_machine.assert_can_transition(
            current, target, resource="Verification",
        )

    @staticmethod
    def assert_draft(verification: Verification) -> None:
        if verification.status != VerificationStatus.DRAFT.value:
            raise ValidationException(message="Verification is no longer a draft")

    @staticmethod
    def assert_property_filled(payload: dict) -> None:
        if not payload.get("propertyType"):
            raise ValidationException(message="Property type is required")
        if not payload.get("state"):
            raise ValidationException(message="Property state is required")
