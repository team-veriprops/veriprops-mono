"""An inbound WhatsApp message is never lost to a failure after Meta was told "received".

The raw message is journalled first, in its own committed write. Only after that is it shown
in the console (claimed with `FOR UPDATE SKIP LOCKED`, each in its own savepoint) and answered
(also in savepoints). So:
- a failed journal write answers Meta with a 5xx, and Meta redelivers;
- a failure after the journal leaves the row unprocessed, and the number's next message or
  the sweep surfaces it;
- a bot failure costs a reply, never the message.
"""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from main.app.domain.channel.whatsapp.inbound.journal import WhatsAppInboundJournal
from main.app.domain.channel.whatsapp.inbound.repo import WhatsAppInboundMessageRepo
from main.app.domain.channel.whatsapp.inbound.service import (
    InboundNotJournalledException,
    WhatsAppInboundService,
)
from main.appodus_utils.db.session import db_session_ctx, is_independent_session
from main.appodus_utils.integrations.messaging.providers.whatsapp.inbound import InboundKind
from main.appodus_utils.integrations.messaging.providers.whatsapp.webhook import WhatsAppWebhookHandler
from test.unit.app.domain.channel.whatsapp.test_inbound_service import _service, inbound


class _Savepoints:
    """Counts savepoints and rolls one back when the block inside it raises."""

    def __init__(self):
        self.opened = 0
        self.rolled_back = 0

    def begin_nested(self):
        tracker = self

        @asynccontextmanager
        async def _sp():
            tracker.opened += 1
            try:
                yield
            except BaseException:
                tracker.rolled_back += 1
                raise

        return _sp()


@pytest.fixture(autouse=True)
def request_session():
    session = MagicMock()
    session.in_transaction.return_value = False
    savepoints = _Savepoints()

    @asynccontextmanager
    async def _begin():
        yield

    session.begin = _begin
    session.begin_nested = savepoints.begin_nested
    session.flush = AsyncMock()
    session.savepoints = savepoints
    token = db_session_ctx.set(session)
    yield session
    db_session_ctx.reset(token)


@pytest.fixture(autouse=True)
def stub_collaborators(monkeypatch):
    from kink import di
    from main.app.domain.channel.whatsapp.bot.surface import WhatsAppAssistantSurface
    from main.app.domain.channel.whatsapp.console_sender import WhatsAppConsoleSender

    bot = MagicMock(handle=AsyncMock())
    monkeypatch.setitem(di._services, WhatsAppConsoleSender, MagicMock(flush=AsyncMock()))
    monkeypatch.setitem(di._services, WhatsAppAssistantSurface, bot)
    return bot


# ── Journal first ────────────────────────────────────────────────────


async def test_a_message_that_cannot_be_journalled_is_refused_for_redelivery():
    svc = _service()
    svc._journal.record = AsyncMock(side_effect=ConnectionError("db down"))

    with pytest.raises(InboundNotJournalledException):
        await svc.ingest(inbound())

    svc._chat.send.assert_not_awaited()


async def test_the_journal_writes_in_its_own_transaction(independent_sessions):
    journal = object.__new__(WhatsAppInboundJournal)
    seen = []

    async def _insert_or_get(values, conflict_columns):
        seen.append(db_session_ctx.get())
        assert conflict_columns == ["wamid"]
        return object(), True

    journal._repo = MagicMock(insert_or_get=AsyncMock(side_effect=_insert_or_get))
    svc = _service()
    await svc.ingest(inbound())  # builds the DTO the journal receives
    dto = svc._journal.record.await_args.args[0]

    assert await journal.record(dto) is True
    assert is_independent_session(seen[0])


# ── Surfacing survives failures ───────────────────────────────────────


async def test_a_failed_surfacing_keeps_the_message_for_a_later_attempt(request_session):
    svc = _service()
    svc._chat.send = AsyncMock(side_effect=RuntimeError("console insert failed"))

    assert await svc.ingest(inbound()) is None  # no raise: Meta still gets its 200

    row = svc._journalled["wamid.A1"]
    assert row.processed_at is None and row.chat_message_id is None
    assert request_session.savepoints.rolled_back == 1


async def test_the_next_message_first_surfaces_the_earlier_one(stub_collaborators):
    svc = _service()
    send = svc._chat.send
    svc._chat.send = AsyncMock(side_effect=RuntimeError("transient"))
    await svc.ingest(inbound(wamid="wamid.A1", text="first"))
    svc._chat.send = send

    record = await svc.ingest(inbound(wamid="wamid.A2", text="second"))

    bodies = [c.args[3] for c in svc._chat.send.await_args_list]
    assert bodies == ["first", "second"]  # the conversation keeps its order
    assert record.wamid == "wamid.A2"
    assert svc._journalled["wamid.A1"].processed_at is not None
    # Only the message in hand is answered; the caught-up one just reaches the console.
    answered = [c.args[0].wamid for c in stub_collaborators.handle.await_args_list]
    assert answered == ["wamid.A2"]


async def test_a_bot_failure_costs_a_reply_not_the_message(stub_collaborators, request_session):
    stub_collaborators.handle = AsyncMock(side_effect=RuntimeError("engine blew up mid-write"))
    svc = _service()

    record = await svc.ingest(inbound())

    assert record is not None and record.processed_at is not None
    assert request_session.savepoints.rolled_back == 1


async def test_a_redelivery_being_handled_elsewhere_is_left_alone():
    svc = _service()
    svc._whatsapp_inbound_message_repo.claim_unprocessed = AsyncMock(return_value=[])  # locked

    assert await svc.ingest(inbound()) is None
    svc._chat.send.assert_not_awaited()


async def test_the_sweep_surfaces_stale_unprocessed_messages():
    svc = _service()
    svc._chat.send = AsyncMock(side_effect=RuntimeError("transient"))
    await svc.ingest(inbound())
    svc._chat.send = AsyncMock(return_value=MagicMock(id="m1", delivered_at=None, date_created=None))
    svc._whatsapp_inbound_message_repo.phones_with_stale_unprocessed = AsyncMock(
        return_value=["+2348012345678"]
    )

    assert await svc.reprocess_stale() == 1
    assert svc._journalled["wamid.A1"].processed_at is not None


# ── The claim is a lock, not a read ──────────────────────────────────


async def test_the_claim_skips_rows_another_request_holds(request_session):
    statements = []

    async def _execute(stmt):
        statements.append(stmt)
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        return result

    request_session.execute = AsyncMock(side_effect=_execute)
    repo = object.__new__(WhatsAppInboundMessageRepo)

    await repo.claim_unprocessed("+2348012345678")

    sql = " ".join(str(statements[0].compile(dialect=postgresql.dialect())).split())
    assert "whatsapp_inbound_messages.processed_at IS NULL" in sql
    assert "ORDER BY whatsapp_inbound_messages.received_at" in sql
    assert sql.endswith("FOR UPDATE SKIP LOCKED")


# ── What the webhook tells Meta ──────────────────────────────────────


def _handler(ingest):
    handler = object.__new__(WhatsAppWebhookHandler)
    handler._status_service = None
    handler._inbound_service = MagicMock(ingest=ingest)
    handler._resolve_inbound_service = lambda: handler._inbound_service
    return handler


def _payload(*wamids):
    return {"entry": [{"changes": [{"value": {
        "messages": [
            {"id": w, "from": "2348012345678", "type": "text", "timestamp": "1700000000",
             "text": {"body": "hi"}}
            for w in wamids
        ]
    }}]}]}


async def test_an_unjournalled_message_answers_meta_with_a_retry_after_the_batch():
    seen = []

    async def _ingest(message):
        seen.append(message.wamid)
        if message.wamid == "wamid.X":
            raise InboundNotJournalledException(message.wamid)

    with pytest.raises(InboundNotJournalledException):
        await _handler(_ingest)._process_handle_webhook_payload(_payload("wamid.X", "wamid.Y"))

    assert seen == ["wamid.X", "wamid.Y"]  # the rest of the batch was still handled


async def test_any_other_failure_is_still_acknowledged():
    async def _ingest(message):
        raise RuntimeError("claim query failed after journalling")

    result = await _handler(_ingest)._process_handle_webhook_payload(_payload("wamid.X"))

    assert result["ingested"] == 0


def test_the_journal_keeps_what_the_console_needs_to_rebuild_the_message():
    svc = object.__new__(WhatsAppInboundService)
    row = MagicMock(
        wamid="w", from_phone="+234", kind=InboundKind.IMAGE.value, text="plan",
        page_code="web-home", interactive_id=None, media_id="m1", media_mime_type="image/jpeg",
        sender_name="Ada", payload={"id": "w"}, received_at=None,
    )

    message = svc._message_from_row(row)

    assert (message.kind, message.text, message.page_code, message.sender_name) == (
        InboundKind.IMAGE, "plan", "web-home", "Ada",
    )
    assert message.raw == {"id": "w"}
