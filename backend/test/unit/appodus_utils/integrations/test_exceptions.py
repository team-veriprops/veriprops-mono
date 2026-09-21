"""Integration exceptions must render as the API's error envelope.

These cross a request boundary — a provider failing during an OTP send reaches the global
handler — and `appodus_exception_handler` reads `exc.status_code` and `exc.code`. The class
never called `super().__init__`, so neither attribute existed and the handler raised
`AttributeError` while handling the error: the caller got an unmapped 500 instead of the
envelope. (`args` was always populated by `Exception.__new__`, which is why `str(exc)` looked
fine and the gap stayed hidden.)
"""
from datetime import datetime, timezone

from fastapi import status

from main.appodus_utils.exception.exception_handlers import exception_json_response
from main.appodus_utils.integrations.exception.exceptions import (
    IntegrationException,
    IntegrationFatalException,
    IntegrationRateLimitException,
    IntegrationValidationException,
)


class TestIntegrationExceptionEnvelope:
    def test_carries_a_gateway_status_and_code(self):
        exc = IntegrationException("provider refused the message")

        assert exc.status_code == status.HTTP_502_BAD_GATEWAY
        assert exc.code == "INTEGRATION_ERROR"

    def test_still_reads_as_its_message(self):
        # Existing provider tests match on the message text, so this must not drift.
        assert str(IntegrationException("invalid recipient")) == "invalid recipient"

    def test_renders_through_the_shared_error_envelope(self):
        response = exception_json_response(IntegrationException("smtp is down"))

        assert response.status_code == status.HTTP_502_BAD_GATEWAY

    def test_subclasses_inherit_the_envelope(self):
        exc = IntegrationFatalException("misconfigured provider")

        assert exc.status_code == status.HTTP_502_BAD_GATEWAY
        assert exc.code == "INTEGRATION_ERROR"

    def test_a_rate_limited_provider_is_429_not_502(self):
        exc = IntegrationRateLimitException("email", datetime.now(timezone.utc))

        assert exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert exc.code == "INTEGRATION_RATE_LIMIT"
        assert "Rate limit exceeded for 'email'" in str(exc)

    def test_a_rejected_payload_is_422_not_502(self):
        exc = IntegrationValidationException("bad payload")

        assert exc.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert exc.code == "INTEGRATION_VALIDATION_ERROR"
        assert "bad payload" in str(exc)
