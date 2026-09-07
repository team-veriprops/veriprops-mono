"""WhatsAppWindowService (PRD §26.7, WA-41).

Meta delivers free text only within 24 hours of the customer's last message; outside it,
only an approved template. The safe failure direction is what these tests pin: when in
doubt — no history, exactly on the boundary — the window reads **closed**, because the
cost of a needless template is a template, while the cost of a wrongly-assumed open
window is a message the customer never receives.
"""
from contextlib import asynccontextmanager
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.channel.whatsapp.window import WhatsAppWindowService
from main.appodus_utils import Utils
from main.appodus_utils.db.session import db_session_ctx

PHONE = "+2348012345678"


@pytest.fixture(autouse=True)
def mock_db_session():
    session = MagicMock()
    session.in_transaction.return_value = False

    @asynccontextmanager
    async def _begin():
        yield

    session.begin = _begin
    session.flush = AsyncMock()
    token = db_session_ctx.set(session)
    yield session
    db_session_ctx.reset(token)


def _service(last_received_at):
    svc = object.__new__(WhatsAppWindowService)
    svc._whatsapp_inbound_message_repo = MagicMock()
    svc._whatsapp_inbound_message_repo.last_received_at = AsyncMock(
        return_value=last_received_at
    )
    return svc


class TestIsOpen:
    async def test_open_while_the_customer_spoke_recently(self):
        svc = _service(Utils.datetime_now() - timedelta(hours=23, minutes=59))
        assert await svc.is_open(PHONE) is True

    async def test_closed_once_the_window_has_passed(self):
        svc = _service(Utils.datetime_now() - timedelta(hours=24, minutes=1))
        assert await svc.is_open(PHONE) is False

    async def test_a_number_that_never_wrote_to_us_is_closed(self):
        # Closed, not open: the doubt-direction that costs a template rather than a
        # silently undelivered message.
        svc = _service(None)
        assert await svc.is_open(PHONE) is False

    async def test_asks_in_e164_whatever_form_the_caller_holds(self):
        # Meta hands the console digits; the journal stores E.164. A missed conversion
        # here would make every window look closed and every reply a template.
        svc = _service(Utils.datetime_now())
        await svc.is_open("2348012345678")
        svc._whatsapp_inbound_message_repo.last_received_at.assert_awaited_once_with(PHONE)
