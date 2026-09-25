"""SSE frames: one encoder for both streams, and an entity id can never break a stream.

A pushed event carried a conversation's `uuid.UUID` straight from the ORM row. `json.dumps`
raised on it, which ended the member's whole chat stream until the browser reconnected, so
every live update after it was lost. Ids now encode in their wire form (32-char hex, as DTOs
send them), and the publishers send that form themselves.
"""
import json
import uuid

from main.app.core.realtime.frames import sse_frame


def _data(frame: str) -> dict:
    event_line, data_line, *_ = frame.split("\n")
    assert event_line.startswith("event: ")
    return json.loads(data_line.removeprefix("data: "))


def test_a_frame_is_one_event_and_one_data_line():
    frame = sse_frame("heartbeat", {})
    assert frame == "event: heartbeat\ndata: {}\n\n"


def test_an_entity_id_is_sent_in_its_wire_form():
    conversation_id = uuid.uuid4()

    data = _data(sse_frame("chat_message", {"conversation_id": conversation_id}))

    assert data == {"conversation_id": conversation_id.hex}


def test_nested_ids_encode_too():
    ids = [uuid.uuid4(), uuid.uuid4()]

    data = _data(sse_frame("x", {"items": [{"id": ids[0]}, {"id": ids[1]}]}))

    assert [item["id"] for item in data["items"]] == [i.hex for i in ids]


async def test_the_chat_publishers_send_hex_ids(monkeypatch):
    """Both chat events name the thread in the same wire form the conversation DTOs use."""
    from unittest.mock import AsyncMock, MagicMock

    from main.app.domain.channel.whatsapp.status import service as status_module
    from main.app.domain.channel.whatsapp.status.service import WhatsAppStatusService

    published = []

    async def _publish(event):
        published.append(event)

    monkeypatch.setattr(status_module, "publish_domain_event", _publish)
    conversation = MagicMock(id=uuid.uuid4())
    svc = object.__new__(WhatsAppStatusService)
    svc._participants = MagicMock()
    svc._participants._participant_repo.list_for_conversation = AsyncMock(return_value=[])

    await svc._nudge_members(conversation)

    assert published[0].data == {"conversation_id": conversation.id.hex}
