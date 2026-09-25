"""OTP send and guess limits hold under concurrent requests.

The counters used to be read, incremented and written back, so a burst of requests all read the
same count. Parallel wrong guesses then got more than `OTP_MAX_FAILURES` tries, and parallel sends
more than `OTP_MAX_RESENDS` codes. Each attempt now reserves its slot atomically (a conditional
increment that refuses at the limit without writing), and a code or verified marker is consumed
by exactly one caller.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from main.app.domain.user.auth import otp_service as otp_module
from main.app.domain.user.auth.models import OtpChannel
from main.app.domain.user.auth.otp_service import OtpService
from main.appodus_utils.exception.exceptions import InvalidTokenException, RateLimitException
from main.appodus_utils.integrations.messaging.models import EmailRecipient

_RECIPIENT = EmailRecipient(email="ada@example.com")


class _FakeKv:
    """In-memory store with the SQL store's single-statement semantics."""

    def __init__(self):
        self.values: dict[str, tuple[str, datetime]] = {}

    @staticmethod
    def _now():
        return datetime.now(timezone.utc)

    def _live(self, key):
        entry = self.values.get(key)
        if entry and entry[1] > self._now():
            return entry
        return None

    async def get(self, key):
        entry = self._live(key)
        return entry[0] if entry else None

    async def set(self, key, ttl: timedelta, value):
        self.values[key] = (str(value), self._now() + ttl)

    async def delete(self, key):
        self.values.pop(key, None)

    async def pop(self, key):
        entry = self._live(key)
        self.values.pop(key, None)
        return entry[0] if entry else None

    async def incr(self, key, ttl: timedelta, *, sliding=False, limit=None):
        entry = self._live(key)
        if entry is None:
            self.values[key] = ("1", self._now() + ttl)
            return 1
        count = int(entry[0])
        if limit is not None and count >= limit:
            return None
        expires = self._now() + ttl if sliding else entry[1]
        self.values[key] = (str(count + 1), expires)
        return count + 1


@pytest.fixture
def otp():
    svc = object.__new__(OtpService)
    svc._kv = _FakeKv()
    svc._session_service = AsyncMock()
    svc._failures = AsyncMock()
    return svc


@pytest.fixture(autouse=True)
def no_delivery():
    with patch.object(otp_module, "send_verification_msg", AsyncMock(return_value=True)):
        yield


async def test_resends_are_capped_at_the_limit(otp):
    for _ in range(otp_module.MAX_RESENDS):
        await otp.send_otp(OtpChannel.EMAIL, _RECIPIENT)

    with pytest.raises(RateLimitException):
        await otp.send_otp(OtpChannel.EMAIL, _RECIPIENT)


async def test_a_refused_resend_does_not_extend_the_lockout(otp):
    for _ in range(otp_module.MAX_RESENDS):
        await otp.send_otp(OtpChannel.EMAIL, _RECIPIENT)
    key = otp_module._resend_key(OtpChannel.EMAIL, _RECIPIENT)
    before = otp._kv.values[key]

    with pytest.raises(RateLimitException):
        await otp.send_otp(OtpChannel.EMAIL, _RECIPIENT)

    assert otp._kv.values[key] == before


async def test_concurrent_resends_cannot_exceed_the_limit(otp):
    results = await asyncio.gather(
        *[otp.send_otp(OtpChannel.EMAIL, _RECIPIENT) for _ in range(10)],
        return_exceptions=True,
    )

    sent = [r for r in results if not isinstance(r, Exception)]
    assert len(sent) == otp_module.MAX_RESENDS
    assert all(isinstance(r, RateLimitException) for r in results if isinstance(r, Exception))


async def test_wrong_guesses_are_capped_then_even_the_right_code_is_refused(otp):
    await otp.send_otp(OtpChannel.EMAIL, _RECIPIENT)
    code = await otp._kv.get(otp_module._otp_key(OtpChannel.EMAIL, _RECIPIENT))

    for _ in range(otp_module.MAX_FAILURES):
        with pytest.raises(InvalidTokenException):
            await otp.verify_otp(OtpChannel.EMAIL, _RECIPIENT, "000000")

    with pytest.raises(RateLimitException):
        await otp.verify_otp(OtpChannel.EMAIL, _RECIPIENT, code)


async def test_the_right_code_still_works_on_the_last_allowed_attempt(otp):
    await otp.send_otp(OtpChannel.EMAIL, _RECIPIENT)
    code = await otp._kv.get(otp_module._otp_key(OtpChannel.EMAIL, _RECIPIENT))
    for _ in range(otp_module.MAX_FAILURES - 1):
        with pytest.raises(InvalidTokenException):
            await otp.verify_otp(OtpChannel.EMAIL, _RECIPIENT, "000000")

    await otp.verify_otp(OtpChannel.EMAIL, _RECIPIENT, code)

    assert await otp.is_recently_verified(OtpChannel.EMAIL, _RECIPIENT.email)
    assert await otp._kv.get(otp_module._failure_key(OtpChannel.EMAIL, _RECIPIENT)) is None


async def test_concurrent_wrong_guesses_cannot_exceed_the_limit(otp):
    await otp.send_otp(OtpChannel.EMAIL, _RECIPIENT)

    results = await asyncio.gather(
        *[otp.verify_otp(OtpChannel.EMAIL, _RECIPIENT, "000000") for _ in range(20)],
        return_exceptions=True,
    )

    judged = [r for r in results if isinstance(r, InvalidTokenException)]
    assert len(judged) == otp_module.MAX_FAILURES
    assert all(isinstance(r, (InvalidTokenException, RateLimitException)) for r in results)


async def test_a_code_verifies_only_once(otp):
    await otp.send_otp(OtpChannel.EMAIL, _RECIPIENT)
    code = await otp._kv.get(otp_module._otp_key(OtpChannel.EMAIL, _RECIPIENT))

    results = await asyncio.gather(
        otp.verify_otp(OtpChannel.EMAIL, _RECIPIENT, code),
        otp.verify_otp(OtpChannel.EMAIL, _RECIPIENT, code),
        return_exceptions=True,
    )

    assert sum(r is None for r in results) == 1
    assert sum(isinstance(r, InvalidTokenException) for r in results) == 1


async def test_a_wrong_guess_is_logged_by_the_independent_recorder(otp):
    """The failure event must survive the InvalidTokenException that follows it."""
    await otp.send_otp(OtpChannel.EMAIL, _RECIPIENT)

    with pytest.raises(InvalidTokenException):
        await otp.verify_otp(OtpChannel.EMAIL, _RECIPIENT, "000000")

    otp._failures.record_event.assert_awaited_once()
    otp._session_service.record_event.assert_awaited_once()  # only the OTP_SENT event


async def test_a_verified_marker_is_consumed_by_one_caller(otp):
    await otp._kv.set(otp_module._verified_key(OtpChannel.EMAIL, _RECIPIENT.email), timedelta(minutes=5), "1")

    first = await otp.consume_verified_marker(OtpChannel.EMAIL, _RECIPIENT.email)
    second = await otp.consume_verified_marker(OtpChannel.EMAIL, _RECIPIENT.email)

    assert (first, second) == (True, False)
