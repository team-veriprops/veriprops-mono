"""WhatsAppInboundService (PRD §26.3.3, WA-09/WA-12/WA-13).

Where a Meta delivery becomes an ordinary Veriprops conversation. The two properties
under test are the ones the rest of the channel leans on: a redelivery never produces a
second conversation turn, and a WhatsApp message takes the same path as web chat rather
than a parallel one. Deps mocked, no DB.
"""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.channel.whatsapp.inbound.service import WhatsAppInboundService
from main.app.domain.communication.chat_message.models import MessageSource, SenderKind
from main.appodus_utils import Utils
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.integrations.messaging.providers.whatsapp.inbound import (
    InboundKind,
    InboundWhatsAppMessage,
)


@pytest.fixture(autouse=True)
def mock_db_session():
    session = MagicMock()
    session.in_transaction.return_value = False

    @asynccontextmanager
    async def _begin():
        yield

    session.begin = _begin
    session.flush = AsyncMock()
    session.add = MagicMock()
    token = db_session_ctx.set(session)
    yield session
    db_session_ctx.reset(token)


@pytest.fixture(autouse=True)
def stub_console_sender(monkeypatch):
    """Ingestion flushes any agent reply queued while Meta's window was shut (§26.7).

    Stubbed here like every other collaborator: these tests are about what ingestion
    records and answers, and the queue's own behaviour is pinned in
    `test_console_sender.py`.
    """
    from kink import di
    from main.app.domain.channel.whatsapp.console_sender import WhatsAppConsoleSender

    sender = MagicMock(flush=AsyncMock())
    monkeypatch.setitem(di._services, WhatsAppConsoleSender, sender)
    return sender


def journal_row(dto, **over) -> SimpleNamespace:
    """A journal row as the journal would hold it for *dto*."""
    row = SimpleNamespace(
        id=Utils.generate_uuid(), wamid=dto.wamid, from_phone=dto.from_phone,
        kind=getattr(dto.kind, "value", dto.kind), text=dto.text, page_code=dto.page_code,
        interactive_id=dto.interactive_id, media_id=dto.media_id,
        media_mime_type=dto.media_mime_type, sender_name=dto.sender_name,
        payload=dto.payload, received_at=dto.received_at,
        chat_message_id=None, processed_at=None, deleted=False,
    )
    for key, value in over.items():
        setattr(row, key, value)
    return row


def _service(existing=None, linked_user_id=None):
    """The service over an in-memory journal.

    `svc._journal.record` behaves like the real one (a first write wins, a repeat wamid is
    refused) and `claim_unprocessed` hands back the number's rows not yet surfaced.
    """
    svc = object.__new__(WhatsAppInboundService)
    svc._whatsapp_inbound_message_repo = MagicMock()
    svc._conversations = MagicMock()
    svc._chat = MagicMock()
    svc._whatsapp_link_service = MagicMock()
    svc._whatsapp_link_service.resolve_user_for_phone = AsyncMock(return_value=linked_user_id)

    journal = {}
    if existing is not None:
        journal[existing.wamid] = existing

    async def _record(dto):
        if dto.wamid in journal:
            return False
        journal[dto.wamid] = journal_row(dto)
        return True

    async def _claim(phone):
        return [r for r in journal.values() if r.from_phone == phone and r.processed_at is None]

    svc._journal = MagicMock(record=AsyncMock(side_effect=_record))
    svc._journalled = journal
    svc._whatsapp_inbound_message_repo.claim_unprocessed = AsyncMock(side_effect=_claim)
    svc._whatsapp_inbound_message_repo._session = MagicMock()
    svc._conversations.get_or_create_whatsapp_thread = AsyncMock(
        return_value=SimpleNamespace(
            id="conv-1", type="GENERAL_SUPPORT", verification_id=None,
            channel="WHATSAPP", external_ref="+2348012345678",
        )
    )
    svc._chat.send = AsyncMock(return_value=SimpleNamespace(
        id=Utils.generate_uuid(), delivered_at=Utils.datetime_now(), date_created=Utils.datetime_now(),
    ))
    svc._participants = MagicMock(advance_read=AsyncMock(return_value=True))
    return svc


def inbound(**over) -> InboundWhatsAppMessage:
    base = dict(
        wamid="wamid.A1", from_phone="+2348012345678", kind=InboundKind.TEXT,
        text="How much for a Lagos land check?", raw={"id": "wamid.A1"},
    )
    base.update(over)
    return InboundWhatsAppMessage(**base)


class TestIngest:
    async def test_records_the_delivery_and_posts_it_to_the_console(self):
        svc = _service()
        record = await svc.ingest(inbound())

        assert record is not None
        svc._chat.send.assert_awaited_once()
        conversation, sender_user_id, sender_kind, body = svc._chat.send.await_args.args
        assert conversation.id == "conv-1"
        # Identity is never taken from the message — the sender is a phone number until
        # the linking flow says otherwise (§26.4.3 conversation-hijack defense).
        assert sender_user_id is None
        assert sender_kind == SenderKind.CUSTOMER
        assert body == "How much for a Lagos land check?"

    async def test_labels_the_message_as_whatsapp_sourced(self):
        svc = _service()
        await svc.ingest(inbound())
        kwargs = svc._chat.send.await_args.kwargs
        assert kwargs["source"] == MessageSource.WHATSAPP
        assert kwargs["external_message_id"] == "wamid.A1"

    async def test_threads_are_keyed_on_the_sender_number(self):
        svc = _service()
        await svc.ingest(inbound())
        assert svc._conversations.get_or_create_whatsapp_thread.await_args.args[0] == (
            "+2348012345678"
        )

    async def test_a_linked_numbers_thread_is_opened_for_its_owner(self):
        """A customer who linked on the website before ever messaging has no thread until
        this first inbound. Resolving the owner through the channel's single identity
        lookup means the thread is born visible to them rather than orphaned."""
        svc = _service(linked_user_id="user-1")
        await svc.ingest(inbound())

        svc._whatsapp_link_service.resolve_user_for_phone.assert_awaited_once_with("+2348012345678")
        assert svc._conversations.get_or_create_whatsapp_thread.await_args.kwargs["user_id"] == "user-1"
        # The owner is the thread's, never the message's: the sender stays a phone number.
        assert svc._chat.send.await_args.args[1] is None

    async def test_an_unlinked_numbers_thread_has_no_owner(self):
        svc = _service(linked_user_id=None)
        await svc.ingest(inbound())
        assert svc._conversations.get_or_create_whatsapp_thread.await_args.kwargs["user_id"] is None

    async def test_links_the_journal_row_to_the_console_message(self):
        # The audit trail from a console message back to exactly what Meta delivered.
        svc = _service()
        record = await svc.ingest(inbound())
        assert record.chat_message_id
        assert record.processed_at is not None


class TestRedelivery:
    async def test_a_repeat_wamid_produces_no_second_message(self):
        # Meta retries until it gets a 2xx, so repeats are expected traffic rather than
        # an error path.
        svc = _service(existing=SimpleNamespace(
            id="already", wamid="wamid.A1", from_phone="+2348012345678",
            processed_at=Utils.datetime_now(),
        ))
        assert await svc.ingest(inbound()) is None
        svc._chat.send.assert_not_awaited()


class TestNonTextInbound:
    async def test_a_caption_is_shown_as_the_customer_wrote_it(self):
        svc = _service()
        await svc.ingest(inbound(kind=InboundKind.IMAGE, text="my survey plan"))
        assert svc._chat.send.await_args.args[3] == "my survey plan"

    @pytest.mark.parametrize(
        "kind,expected",
        [
            (InboundKind.IMAGE, "[sent an image]"),
            (InboundKind.DOCUMENT, "[sent a document]"),
            (InboundKind.AUDIO, "[sent a voice note]"),
            (InboundKind.LOCATION, "[shared a location pin]"),
            (InboundKind.CONTACTS, "[shared a contact card]"),
            (InboundKind.UNSUPPORTED, "[sent an unsupported message type]"),
        ],
    )
    async def test_every_non_text_type_reaches_the_console_labelled(self, kind, expected):
        # §26.6.3: nothing is silently dropped — an agent always sees that something came
        # in, and what kind of thing it was.
        svc = _service()
        await svc.ingest(inbound(kind=kind, text=None))
        assert svc._chat.send.await_args.args[3] == expected

    async def test_a_console_message_is_never_empty(self):
        svc = _service()
        await svc.ingest(inbound(text=None))
        assert svc._chat.send.await_args.args[3].strip()


class TestThreadSubject:
    async def test_uses_the_whatsapp_profile_name_when_meta_supplies_one(self):
        svc = _service()
        await svc.ingest(inbound(sender_name="Ada"))
        assert svc._conversations.get_or_create_whatsapp_thread.await_args.kwargs[
            "subject"
        ] == "WhatsApp · Ada"

    async def test_falls_back_to_a_generic_subject(self):
        svc = _service()
        await svc.ingest(inbound())
        assert svc._conversations.get_or_create_whatsapp_thread.await_args.kwargs[
            "subject"
        ] == "WhatsApp enquiry"


class TestWidgetAttribution:
    """§26.4.1's `[ref: …]` marker, lifted out at ingest (§26.10, D85).

    It happens here rather than in the Meta normalizer for a determinism reason: `ingest`
    is the single funnel both doors pass through — the signed webhook and
    `POST /dev/whatsapp/inbound` — and extracting it upstream gave the two doors different
    behaviour, so a page code arrived in production and never in an automated run.
    """

    async def test_the_page_code_is_lifted_off_the_message(self):
        svc = _service()

        await svc.ingest(inbound(text="Hi Veriprops! [ref: web-pricing]"))

        written = svc._journal.record.await_args.args[0]
        assert written.page_code == "web-pricing"

    async def test_the_marker_never_reaches_the_console_or_the_classifier(self):
        # The customer did not type it — their phone did. An agent reading the thread must
        # see the message the customer believes they sent.
        svc = _service()

        await svc.ingest(inbound(text="Hi Veriprops! [ref: web-home]"))

        _conversation, _sender, _kind, body = svc._chat.send.await_args.args
        assert body == "Hi Veriprops!"

    async def test_an_ordinary_message_is_untouched(self):
        svc = _service()

        await svc.ingest(inbound(text="How much for a Lagos land check?"))

        written = svc._journal.record.await_args.args[0]
        assert written.page_code is None
        assert written.text == "How much for a Lagos land check?"

    async def test_a_message_that_is_only_a_marker_still_opens_the_conversation(self):
        # The widget's prefill is editable, and a customer who deletes the greeting and
        # sends the bare marker is starting a conversation like anyone else.
        svc = _service()

        record = await svc.ingest(inbound(text="[ref: web-home]"))

        assert record is not None
        written = svc._journal.record.await_args.args[0]
        assert written.page_code == "web-home"
        assert written.text is None


class TestWritingBackCountsAsReading:
    """The fallback for customers with read receipts off (D92): a customer who writes on
    WhatsApp has seen the thread, so their portal badge clears without a receipt."""

    async def test_a_linked_customers_message_reads_the_thread_for_them(self):
        svc = _service(linked_user_id="user-1")

        await svc.ingest(inbound())

        [conversation_id, user_id, at] = svc._participants.advance_read.await_args.args
        assert (conversation_id, user_id) == ("conv-1", "user-1")
        assert at == svc._chat.send.return_value.delivered_at

    async def test_an_unlinked_number_has_no_portal_to_update(self):
        svc = _service(linked_user_id=None)

        await svc.ingest(inbound())

        svc._participants.advance_read.assert_not_awaited()
