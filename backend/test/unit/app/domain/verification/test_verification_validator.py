"""Unit tests for VerificationValidator.

Covers all static validation methods:
- assert_owner
- assert_draft
- assert_property_filled
- assert_can_transition
"""
from unittest.mock import MagicMock

import pytest

from main.app.domain.verification.models import VerificationStatus
from main.app.domain.verification.validator import VerificationValidator
from main.appodus_utils.exception.exceptions import (
    InvalidResourceStateException,
    ValidationException,
)


def _make_verification(customer_id: str = "cust-001", status: VerificationStatus = VerificationStatus.DRAFT):
    row = MagicMock()
    row.customer_id = customer_id
    row.status = status.value
    return row


class TestAssertOwner:
    def test_correct_owner_passes(self):
        validator = VerificationValidator()
        row = _make_verification(customer_id="cust-001")
        validator.assert_owner(row, "cust-001")  # no exception

    def test_wrong_owner_raises(self):
        validator = VerificationValidator()
        row = _make_verification(customer_id="other")
        with pytest.raises(ValidationException, match="not owned by"):
            validator.assert_owner(row, "cust-001")


class TestAssertDraft:
    def test_draft_status_passes(self):
        validator = VerificationValidator()
        row = _make_verification(status=VerificationStatus.DRAFT)
        validator.assert_draft(row)  # no exception

    def test_submitted_raises(self):
        validator = VerificationValidator()
        row = _make_verification(status=VerificationStatus.SUBMITTED)
        with pytest.raises(ValidationException, match="no longer a draft"):
            validator.assert_draft(row)

    def test_paid_raises(self):
        validator = VerificationValidator()
        row = _make_verification(status=VerificationStatus.PAID)
        with pytest.raises(ValidationException):
            validator.assert_draft(row)


class TestAssertPropertyFilled:
    def test_valid_payload_passes(self):
        VerificationValidator.assert_property_filled({"propertyType": "LAND", "state": "LAGOS"})

    def test_missing_property_type_raises(self):
        with pytest.raises(ValidationException, match="Property type is required"):
            VerificationValidator.assert_property_filled({"state": "LAGOS"})

    def test_empty_property_type_raises(self):
        with pytest.raises(ValidationException, match="Property type is required"):
            VerificationValidator.assert_property_filled({"propertyType": "", "state": "LAGOS"})

    def test_missing_state_raises(self):
        with pytest.raises(ValidationException, match="Property state is required"):
            VerificationValidator.assert_property_filled({"propertyType": "BUILDING"})

    def test_empty_payload_raises(self):
        with pytest.raises(ValidationException):
            VerificationValidator.assert_property_filled({})


class TestAssertCanTransition:
    def test_valid_draft_to_submitted(self):
        VerificationValidator.assert_can_transition("DRAFT", "SUBMITTED")  # no exception

    def test_valid_payment_pending_to_paid(self):
        VerificationValidator.assert_can_transition("PAYMENT_PENDING", "PAID")

    def test_invalid_draft_to_completed_raises(self):
        with pytest.raises(InvalidResourceStateException):
            VerificationValidator.assert_can_transition("DRAFT", "COMPLETED")

    def test_invalid_terminal_to_any_raises(self):
        with pytest.raises(InvalidResourceStateException):
            VerificationValidator.assert_can_transition("CANCELLED", "DRAFT")
