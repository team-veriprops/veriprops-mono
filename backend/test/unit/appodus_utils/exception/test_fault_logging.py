"""One ERROR per real fault, with its traceback; nothing at ERROR for an expected outcome.

Every decorated layer (repo, service, transaction, session scope) used to log each exception at
ERROR with a traceback — a refused link, a lost race, a wrong password — so one ordinary 4xx
produced a screenful of tracebacks and a real fault was lost among them. Now:

- an expected outcome (a 4xx, a domain refusal, a unique violation the caller declared) is never
  logged above DEBUG by the layers it passes through;
- a real fault is logged once, at the first layer that sees it, with its traceback and the
  request's reference, and every outer layer (and the global handler) recognises it as logged —
  so even a fault a best-effort caller swallows still leaves exactly one ERROR behind.
"""
import logging
from contextlib import asynccontextmanager
from unittest.mock import MagicMock

import pytest
from kink import di
from sqlalchemy.exc import IntegrityError

from main.app.domain.channel.whatsapp.handoff.tokens import HandoffTokenError
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import ValidationException
from main.appodus_utils.exception.faults import expecting_violation, log_fault_once
from main.appodus_utils.middleware.request_logging_middleware import request_reference_scope


class _Records:
    """Every loguru record emitted while in use: (level name, message, has traceback)."""

    def __enter__(self):
        self.records: list[tuple[str, str, bool]] = []

        def _sink(message):
            record = message.record
            self.records.append((record["level"].name, record["message"], record["exception"] is not None))

        self._id = di["logger"].add(_sink, level="DEBUG")
        return self

    def __exit__(self, *exc):
        di["logger"].remove(self._id)

    @property
    def errors(self):
        return [r for r in self.records if r[0] == "ERROR"]


@pytest.fixture(autouse=True)
def session():
    s = MagicMock()
    s.in_transaction.return_value = True  # join, so nothing tries to begin a real transaction
    token = db_session_ctx.set(s)
    yield s
    db_session_ctx.reset(token)


def _violation(constraint: str) -> IntegrityError:
    orig = Exception(f'duplicate key value violates unique constraint "{constraint}"')
    orig.constraint_name = constraint
    return IntegrityError("INSERT …", {}, orig)


@decorate_all_methods(method_trace_logger)
class _Repo:
    def __init__(self, error: Exception):
        self._error = error

    async def write(self):
        raise self._error


@decorate_all_methods(transactional(), exclude=["__init__"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"])
class _Service:
    def __init__(self, error: Exception):
        self._repo = _Repo(error)

    async def act(self):
        await self._repo.write()

    async def act_swallowing(self):
        try:
            await self._repo.write()
        except Exception:
            return "handled"


class TestExpectedOutcomes:
    @pytest.mark.parametrize("error", [
        ValidationException(message="That number is taken."),
        HandoffTokenError(),
    ], ids=["4xx", "domain-refusal"])
    async def test_pass_through_every_layer_without_an_error_record(self, error):
        with _Records() as log:
            with pytest.raises(type(error)):
                await _Service(error).act()

        assert log.errors == []

    async def test_a_declared_unique_violation_is_an_answer_not_a_fault(self):
        with _Records() as log:
            with expecting_violation("uq_whatsapp_links_phone_e164"):
                with pytest.raises(IntegrityError):
                    await _Service(_violation("uq_whatsapp_links_phone_e164")).act()

        assert log.errors == []

    async def test_an_undeclared_violation_is_still_a_fault(self):
        with _Records() as log:
            with expecting_violation("uq_whatsapp_links_phone_e164"):
                with pytest.raises(IntegrityError):
                    await _Service(_violation("uq_whatsapp_links_user_id")).act()

        assert len(log.errors) == 1


class TestRealFaults:
    async def test_logged_once_with_its_traceback_however_many_layers_it_crosses(self):
        with _Records() as log:
            with pytest.raises(RuntimeError):
                await _Service(RuntimeError("connection reset")).act()

        [(level, message, has_traceback)] = log.errors
        assert has_traceback
        assert "connection reset" in message

    async def test_a_fault_a_caller_swallows_still_leaves_one_error(self):
        with _Records() as log:
            assert await _Service(RuntimeError("smtp down")).act_swallowing() == "handled"

        assert len(log.errors) == 1

    async def test_the_record_carries_the_request_reference(self):
        with _Records() as log:
            with request_reference_scope("AB12CD34"):
                with pytest.raises(RuntimeError):
                    await _Service(RuntimeError("boom")).act()

        [(_, message, _)] = log.errors
        assert message.startswith("[AB12CD34]")

    def test_the_boundary_does_not_log_a_fault_again(self):
        error = RuntimeError("boom")
        with _Records() as log:
            assert log_fault_once(error, "repo") is True
            assert log_fault_once(error, "request", reference="AB12CD34") is False

        assert len(log.errors) == 1

    def test_a_safe_wrapper_raised_from_a_logged_fault_is_not_logged_again(self):
        cause = RuntimeError("provider timed out")
        with _Records() as log:
            log_fault_once(cause, "webhook")
            try:
                raise ValueError("Internal server error") from cause
            except ValueError as wrapper:
                assert log_fault_once(wrapper, "request", reference="AB12CD34") is False

        assert len(log.errors) == 1

    def test_the_boundary_logs_a_fault_nothing_else_saw(self):
        with _Records() as log:
            assert log_fault_once(RuntimeError("boom"), "request", reference="AB12CD34") is True

        [(_, message, has_traceback)] = log.errors
        assert message.startswith("[AB12CD34]") and has_traceback


class TestStdlibLogging:
    """Third-party libraries log through the stdlib; they reach the app's sinks, and the JWT
    library's ordinary 401s (already logged at WARNING by the handler) are silenced."""

    def test_stdlib_records_reach_loguru(self):
        from main.appodus_utils.config.logger import route_stdlib_logging

        route_stdlib_logging("INFO")
        # A logger created now: Alembic's `fileConfig` (run by the migration tests) disables
        # every logger that existed before it, which says nothing about the app's routing.
        library_logger = logging.getLogger(f"third_party.scheduler.{id(self)}")
        with _Records() as log:
            library_logger.warning("job missed its run time")

        assert ("WARNING", "job missed its run time", False) in log.records

    def test_the_jwt_library_is_quiet(self):
        from main.appodus_utils.config.logger import route_stdlib_logging

        route_stdlib_logging("INFO")
        assert not logging.getLogger("libre_fastapi_jwt.auth_jwt").isEnabledFor(logging.ERROR)


async def test_a_session_scope_fault_is_logged_once(monkeypatch):
    """A job's `ALWAYS_NEW` scope is the outermost layer: a fault from its commit still logs once."""
    from main.appodus_utils.db import session as session_module

    factory_session = MagicMock()
    factory_session.info = {}

    @asynccontextmanager
    async def _factory():
        yield factory_session

    monkeypatch.setattr(session_module, "IS_SERVERLESS", False)
    monkeypatch.setattr(session_module, "AsyncSessionLocal", _factory)

    with _Records() as log:
        with pytest.raises(RuntimeError):
            async with session_module.create_new_db_session():
                raise RuntimeError("commit failed")

    assert len(log.errors) == 1
