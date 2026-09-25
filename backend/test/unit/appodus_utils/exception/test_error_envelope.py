"""The API error envelope never hands internals to a client.

A server-side failure is the one error a user can do nothing about, and its raw text is the one most
likely to carry internals — SQL and its parameters, a host error, a provider's reply. So a 5xx
always answers with the same safe sentence plus a short reference, in every environment, and the
real exception goes to the log under that reference, where support can find it from a screenshot.
A 4xx is different: its message is copy written for the user ("Invalid username or password") and
passes through unchanged.
"""
import re

from fastapi import FastAPI
from fastapi.testclient import TestClient
from kink import di

from main.appodus_utils.exception.exception_handlers import (
    SERVER_ERROR_MESSAGE,
    appodus_exception_handler,
    exception_json_response,
    generic_exception_handler,
)
from main.appodus_utils.exception.exceptions import (
    AppodusBaseException,
    InvalidCredentialsException,
)
from main.appodus_utils.integrations.exception.exceptions import IntegrationException
from main.appodus_utils.middleware.request_logging_middleware import (
    REQUEST_ID_HEADER,
    RequestLoggingMiddleware,
)

RAW_DB_TEXT = (
    "(IntegrityError) duplicate key value violates unique constraint \"uq_users_email\" "
    "[SQL: INSERT INTO users ...] [parameters: ('$argon2id$v=19$m=65536...')]"
)
RAW_PROVIDER_TEXT = "AWS SES error (Throttling): Maximum sending rate exceeded for AKIAEXAMPLE"
REFERENCE = re.compile(r"^[0-9A-F]{8}$")


def _client(*, with_request_logging: bool = True) -> TestClient:
    """An app wired the way `veriprops.py` wires the real one."""
    app = FastAPI()
    app.add_exception_handler(AppodusBaseException, appodus_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
    if with_request_logging:
        app.add_middleware(RequestLoggingMiddleware)

    @app.get("/ok")
    def ok():
        return {"ok": True}

    @app.get("/unhandled")
    def unhandled():
        raise RuntimeError(RAW_DB_TEXT)

    @app.get("/provider")
    def provider():
        raise IntegrationException(RAW_PROVIDER_TEXT)

    @app.get("/wrong-password")
    def wrong_password():
        raise InvalidCredentialsException()

    # The generic handler runs in Starlette's outermost middleware, which re-raises after
    # responding; the client must hand back that response rather than the exception.
    return TestClient(app, raise_server_exceptions=False)


class _LogCapture:
    """Collects everything the app logs while in use."""

    def __enter__(self):
        self.lines: list[str] = []
        self._sink = di["logger"].add(lambda message: self.lines.append(str(message)), level="DEBUG")
        return self

    def __exit__(self, *exc):
        di["logger"].remove(self._sink)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


class TestUnhandledFailure:
    def test_answers_with_the_safe_message_and_nothing_else(self):
        body = _client().get("/unhandled").json()["error"]

        assert body["code"] == "INTERNAL_ERROR"
        assert body["message"] == SERVER_ERROR_MESSAGE
        assert set(body) == {"code", "message", "reference"}

    def test_never_carries_the_exception_text_or_a_traceback(self):
        raw = _client().get("/unhandled").text

        assert "IntegrityError" not in raw
        assert "argon2" not in raw
        assert "Traceback" not in raw

    def test_is_a_500(self):
        assert _client().get("/unhandled").status_code == 500

    def test_carries_a_short_reference_that_matches_the_response_header(self):
        response = _client().get("/unhandled")
        reference = response.json()["error"]["reference"]

        assert REFERENCE.match(reference)
        assert response.headers[REQUEST_ID_HEADER] == reference

    def test_logs_the_real_exception_under_that_reference(self):
        with _LogCapture() as log:
            reference = _client().get("/unhandled").json()["error"]["reference"]

        assert reference in log.text
        assert "IntegrityError" in log.text

    def test_still_has_a_reference_when_it_fails_before_request_logging_runs(self):
        # A failure raised by middleware outside the request logger (edge auth, say) has no
        # reference on the request yet; the handler mints one rather than answering without.
        body = _client(with_request_logging=False).get("/unhandled").json()["error"]

        assert REFERENCE.match(body["reference"])


class TestHandledServerFailure:
    def test_a_provider_failure_keeps_its_status_and_code_but_not_its_text(self):
        response = _client().get("/provider")
        body = response.json()["error"]

        assert response.status_code == 502
        assert body["code"] == "INTEGRATION_ERROR"
        assert body["message"] == SERVER_ERROR_MESSAGE
        assert "AKIA" not in response.text

    def test_logs_the_provider_text_under_the_reference(self):
        with _LogCapture() as log:
            reference = _client().get("/provider").json()["error"]["reference"]

        assert reference in log.text
        assert RAW_PROVIDER_TEXT in log.text


class TestClientError:
    def test_passes_its_message_through_because_it_was_written_for_the_user(self):
        response = _client().get("/wrong-password")
        body = response.json()["error"]

        assert response.status_code == 401
        assert body["code"] == "INVALID_CREDENTIALS"
        assert body["message"] == "Invalid username or password"
        assert REFERENCE.match(body["reference"])


class TestEveryResponse:
    def test_a_successful_response_carries_its_reference_too(self):
        assert REFERENCE.match(_client().get("/ok").headers[REQUEST_ID_HEADER])


class TestEnvelopeBuilder:
    """`exception_json_response` is also called directly by endpoints that must *return* an error."""

    def test_sanitises_a_server_error_with_no_reference_to_hand(self):
        body = exception_json_response(IntegrationException(RAW_PROVIDER_TEXT)).body.decode()

        assert SERVER_ERROR_MESSAGE in body
        assert "AKIA" not in body

    def test_passes_a_client_error_through(self):
        body = exception_json_response(InvalidCredentialsException()).body.decode()

        assert "Invalid username or password" in body
