"""Subscribers (§4.8): the realtime subscriber re-emits the exact S13 SSE event name so the
customer tracking hooks are untouched; the chat-counter subscriber pushes only chat events."""
from unittest.mock import AsyncMock, MagicMock

from kink import di

from main.app.core.events.events import DomainEvent, EventType
from main.app.core.events.subscribers import (
    chat_autopost_subscriber,
    chat_counter_subscriber,
    realtime_subscriber,
)
from main.app.core.realtime.emitter import VerificationEventEmitter, VerificationEventType
from main.app.core.realtime.user_emitter import UserEventEmitter, UserEventType
from main.app.domain.communication.service import CommunicationService


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


async def test_chat_autopost_subscriber_posts_status_change_to_customer_thread():
    """G1: a status change auto-posts a SYSTEM breadcrumb into the customer↔admin thread (§11.1)."""
    original = di[CommunicationService]
    spy = MagicMock()
    spy.auto_post_customer = AsyncMock()
    di[CommunicationService] = spy
    try:
        await chat_autopost_subscriber(DomainEvent(
            type=EventType.STATUS_CHANGED, verification_id="v-1",
            recipient_user_ids=("cust-1",), data={"status": "IN_PROGRESS"},
        ))
        spy.auto_post_customer.assert_awaited_once()
        args = spy.auto_post_customer.call_args.args
        assert args[0] == "v-1" and args[1] == "cust-1"
    finally:
        di[CommunicationService] = original


async def test_chat_autopost_ignores_non_status_events():
    original = di[CommunicationService]
    spy = MagicMock()
    spy.auto_post_customer = AsyncMock()
    di[CommunicationService] = spy
    try:
        await chat_autopost_subscriber(DomainEvent(
            type=EventType.MESSAGE_SENT, verification_id="v-1", recipient_user_ids=("cust-1",),
        ))
        spy.auto_post_customer.assert_not_called()
    finally:
        di[CommunicationService] = original
