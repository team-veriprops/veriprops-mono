"""VerificationMessages senders that address a raw recipient rather than a registered user."""
from unittest.mock import AsyncMock

from main.app.domain.message.verification_messages import VerificationMessages
from main.appodus_utils.integrations.messaging.models import MessageChannel


async def test_report_share_is_addressed_to_the_raw_email():
    """A named share's recipient need not have an account (§13.2): the message must be
    addressed to the plain email string the customer typed, which the router reads as-is."""
    sender = object.__new__(VerificationMessages)
    sender._send_direct_message = AsyncMock()

    await sender.send_report_share(
        recipient_email="friend@example.com", vid="VP-ABC123",
        share_url="https://veriprops.ng/shared/tok-123",
    )

    kwargs = sender._send_direct_message.await_args.kwargs
    assert kwargs["recipient"].email == "friend@example.com"
    assert kwargs["default_channels"] == [MessageChannel.EMAIL]
