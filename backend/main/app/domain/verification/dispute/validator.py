from kink import inject

from main.app.domain.verification.models import VerificationStatus
from main.appodus_utils.exception.exceptions import ValidationException

_MIN_DESCRIPTION_LENGTH = 100


@inject
class DisputeValidator:
    def assert_can_dispute(self, status: str) -> None:
        if VerificationStatus(status) != VerificationStatus.COMPLETED:
            raise ValidationException(message="Disputes can only be filed on COMPLETED verifications")

    def assert_description_length(self, description: str) -> None:
        if len(description.strip()) < _MIN_DESCRIPTION_LENGTH:
            raise ValidationException(
                message=f"Dispute description must be at least {_MIN_DESCRIPTION_LENGTH} characters"
            )
