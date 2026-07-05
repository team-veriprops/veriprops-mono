"""Subscribers (§4.8): the realtime subscriber re-emits the exact S13 SSE event name so the
customer tracking hooks are untouched; the chat-counter subscriber pushes only chat events."""
from unittest.mock import MagicMock

import pytest
from kink import di

from main.app.core.events.events import DomainEvent, EventType
from main.app.core.events.subscribers import chat_counter_subscriber, realtime_subscriber
from main.app.core.realtime.emitter import VerificationEventEmitter, VerificationEventType
from main.app.core.realtime.user_emitter import UserEventEmitter, UserEventType


async def test_realtime_subscriber_reemits_the_same_sse_event_name():
    original = di[VerificationEventEmitter]
    spy = MagicMock()
    di[VerificationEventEmitter] = spy
    try:
        await realtime_subscriber(DomainEvent(
            type=EventType.STATUS_CHANGED, verification_id="v-1",
            sse_event=VerificationEventType.STATUS_CHANGED.value, data={"status": "PAID"},
        ))
        spy.publish.assert_called_once_with(
            "v-1", VerificationEventType.STATUS_CHANGED, {"status": "PAID"}
        )
    finally:
        di[VerificationEventEmitter] = original


async def test_realtime_subscriber_ignores_events_without_an_sse_event():
    original = di[VerificationEventEmitter]
    spy = MagicMock()
    di[VerificationEventEmitter] = spy
    try:
        await realtime_subscriber(DomainEvent(type=EventType.CONFLICT_FLAGGED, verification_id="v-1"))
        spy.publish.assert_not_called()
    finally:
        di[VerificationEventEmitter] = original


async def test_chat_counter_subscriber_pushes_only_chat_events():
    original = di[UserEventEmitter]
    spy = MagicMock()
    di[UserEventEmitter] = spy
    try:
        # A non-chat event does nothing.
        await chat_counter_subscriber(DomainEvent(type=EventType.STATUS_CHANGED, recipient_user_ids=("u-1",)))
        spy.publish.assert_not_called()
        # A chat event pushes the counter to each recipient.
        await chat_counter_subscriber(DomainEvent(
            type=EventType.MESSAGE_SENT, recipient_user_ids=("u-1",), data={"conversation_id": "c-1"},
        ))
        pushed = {c.args[1] for c in spy.publish.call_args_list}
        assert UserEventType.CHAT_MESSAGE in pushed
        assert UserEventType.CHAT_UNREAD in pushed
    finally:
        di[UserEventEmitter] = original
