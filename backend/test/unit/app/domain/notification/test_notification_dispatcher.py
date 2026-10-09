"""NotificationDispatcher — the email/SMS leg of a notification goes out on the channels the
rule table and the user's preferences chose (§12.1, §4.8), and nowhere when they chose none."""
from unittest.mock import AsyncMock

from main.app.domain.notification.dispatcher import NotificationDispatcher
from main.appodus_utils.integrations.messaging.models import (
    MessageCategory,
    MessageChannel,
    MessageContextModule,
    MessageRecipientUserId,
)
from main.appodus_utils.integrations.messaging.templating.models import AvailableTemplate

_TEMPLATE = next(iter(AvailableTemplate))


def _dispatcher():
    dispatcher = object.__new__(NotificationDispatcher)
    dispatcher._send_message = AsyncMock()
    return dispatcher


async def test_sends_the_template_to_the_user_on_exactly_the_chosen_channels():
    dispatcher = _dispatcher()

    await dispatcher.dispatch("u1", _TEMPLATE, [MessageChannel.EMAIL, MessageChannel.SMS], {"vid": "VP-1"})

    dispatcher._send_message.assert_awaited_once_with(
        recipient_user_id=MessageRecipientUserId(user_id="u1"),
        template=_TEMPLATE,
        context_modules=[MessageContextModule.USER],
        category=MessageCategory.TRANSACTION,
        default_channels=[MessageChannel.EMAIL, MessageChannel.SMS],
        extra_context={"vid": "VP-1"},
        queued=False,
    )


async def test_a_queued_notification_is_handed_on_as_queued():
    dispatcher = _dispatcher()

    await dispatcher.dispatch("u1", _TEMPLATE, [MessageChannel.EMAIL], {"vid": "VP-1"}, queued=True)

    assert dispatcher._send_message.call_args.kwargs["queued"] is True


async def test_no_chosen_channel_sends_nothing():
    dispatcher = _dispatcher()

    await dispatcher.dispatch("u1", _TEMPLATE, [])

    dispatcher._send_message.assert_not_awaited()


async def test_an_empty_context_is_passed_as_none():
    dispatcher = _dispatcher()

    await dispatcher.dispatch("u1", _TEMPLATE, [MessageChannel.EMAIL], {})

    assert dispatcher._send_message.call_args.kwargs["extra_context"] is None
