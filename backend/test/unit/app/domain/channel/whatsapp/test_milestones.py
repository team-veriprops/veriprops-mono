"""WhatsAppMilestoneSender — the three gates on a §7.6.2 milestone (D65/D75, WA-16/34/35).

Every assertion here is about something *not* happening, because that is where this module
earns its keep. A milestone is a business-initiated message carrying case details, so the
ways it can be wrong are all leaks:

* sending to a customer who never opted in (§7.4.6),
* sending to `users.phone` — a profile number nobody proved control of over WhatsApp,
  which is §7.4.3's leak running outwards (D65), and
* sending a report link that will be dead by the time it is read (D75).

The fourth property is that none of these are errors: a milestone is a courtesy on top of a
state change that already happened, so a gate that closes — or a transport that throws —
must never break the transaction that moved the case.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.core.state.status import VerificationStatus
from main.app.domain.channel.whatsapp.milestones import (
    WhatsAppMilestoneSender,
    status_label_for,
)
from main.appodus_utils.integrations.messaging.models import MessageContext
from main.appodus_utils.integrations.messaging.templating.models import AvailableTemplate

PHONE = "+2348012345678"
USER = "user-1"
CASE = "case-1"
VID = "VP-2026-0042"


@pytest.fixture(autouse=True)
def outbound_enabled(monkeypatch):
    from main.app.config import settings as settings_module

    monkeypatch.setattr(settings_module.settings, "ENABLE_OUT_MESSAGING", True)
    monkeypatch.setattr(
        settings_module.settings, "PUBLIC_APP_BASE_URL", "https://veriprops.ng"
    )


@pytest.fixture
def messages(monkeypatch):
    """Capture sends at the message-sender boundary, short of the messaging pipeline.

    Patched on the **class** rather than swapped into the DI container: kink memoizes a
    resolved singleton, so an entry pushed into `di._services` loses to an instance an
    earlier test already built — a substitution that works alone and silently stops
    working once the suite runs in a different order.
    """
    from main.app.domain.message.verification_messages import VerificationMessages

    sender = MagicMock()
    sender.send_whatsapp_milestone = AsyncMock()
    sender.send_whatsapp_delegate_status = AsyncMock()
    monkeypatch.setattr(
        VerificationMessages, "send_whatsapp_milestone", sender.send_whatsapp_milestone
    )
    monkeypatch.setattr(
        VerificationMessages,
        "send_whatsapp_delegate_status",
        sender.send_whatsapp_delegate_status,
    )
    return sender


def _verification(status=VerificationStatus.PAID):
    return SimpleNamespace(id=CASE, vid=VID, customer_id=USER, status=status.value)


def _sender(*, consented=True, phone=PHONE, verification=None):
    svc = object.__new__(WhatsAppMilestoneSender)
    svc._whatsapp_consent_service = MagicMock(
        utility_granted=AsyncMock(return_value=consented)
    )
    svc._whatsapp_link_service = MagicMock(
        resolve_phone_for_user=AsyncMock(return_value=phone)
    )
    svc._verification_repo = MagicMock(
        get_model=AsyncMock(
            return_value=verification if verification is not None else _verification()
        )
    )
    return svc


def _sent(messages):
    return messages.send_whatsapp_milestone.await_args_list


class TestTheConsentGate:
    async def test_a_consented_customer_gets_the_template(self, messages):
        svc = _sender()
        await svc.send_customer_milestone(
            USER, CASE, AvailableTemplate.WHATSAPP_PAYMENT_CONFIRMED
        )
        assert len(_sent(messages)) == 1
        assert (
            _sent(messages)[0].kwargs["template"]
            is AvailableTemplate.WHATSAPP_PAYMENT_CONFIRMED
        )

    async def test_no_consent_means_no_send(self, messages):
        """WA-27: enforcement is in the router's path, not at the send site, and this is
        the assertion that it actually stops something."""
        svc = _sender(consented=False)
        await svc.send_customer_milestone(
            USER, CASE, AvailableTemplate.WHATSAPP_PAYMENT_CONFIRMED
        )
        assert _sent(messages) == []

    async def test_a_closed_gate_is_not_an_error(self, messages):
        """It returns rather than raising: the payment that triggered this already
        happened, and rolling it back over a messaging preference would be absurd."""
        svc = _sender(consented=False)
        await svc.send_customer_milestone(
            USER, CASE, AvailableTemplate.WHATSAPP_PAYMENT_CONFIRMED
        )  # no exception


class TestTheRecipientGate:
    async def test_consent_without_a_linked_number_sends_nothing(self, messages):
        """D65: the only valid address is the OTP-verified linked number. A customer who
        ticked the box but never linked has nowhere to receive — and inventing a
        destination from their profile is the leak this gate exists to prevent."""
        svc = _sender(phone=None)
        await svc.send_customer_milestone(
            USER, CASE, AvailableTemplate.WHATSAPP_REPORT_READY
        )
        assert _sent(messages) == []

    async def test_the_address_is_the_linked_number(self, messages):
        svc = _sender()
        await svc.send_customer_milestone(
            USER, CASE, AvailableTemplate.WHATSAPP_PAYMENT_CONFIRMED
        )
        recipient = _sent(messages)[0].kwargs["recipient"]
        assert PHONE.endswith(str(recipient.phone.international_number).replace(" ", "")[-10:])

    async def test_the_link_service_is_asked_by_user_not_by_profile_phone(self, messages):
        svc = _sender()
        await svc.send_customer_milestone(
            USER, CASE, AvailableTemplate.WHATSAPP_PAYMENT_CONFIRMED
        )
        svc._whatsapp_link_service.resolve_phone_for_user.assert_awaited_once_with(USER)


class TestTemplateContext:
    async def test_a_milestone_carries_the_case_reference(self, messages):
        svc = _sender()
        await svc.send_customer_milestone(
            USER, CASE, AvailableTemplate.WHATSAPP_VERIFICATION_STARTED
        )
        context = _sent(messages)[0].kwargs["context"]
        assert context[MessageContext.SHARE_VID] == VID

    async def test_report_ready_links_to_the_portal_not_a_handoff_token(self, messages):
        """D75. A §7.5 token lives fifteen minutes; a milestone is read whenever the
        customer next opens WhatsApp, so a token here would send most readers to the
        expiry page from a message they never clicked."""
        svc = _sender(verification=_verification(VerificationStatus.COMPLETED))
        await svc.send_customer_milestone(
            USER, CASE, AvailableTemplate.WHATSAPP_REPORT_READY
        )
        link = _sent(messages)[0].kwargs["context"][MessageContext.LINK]
        assert link == f"https://veriprops.ng/portal/verifications/{VID}"
        assert "/wa/report/" not in link

    async def test_only_report_ready_carries_a_link(self, messages):
        """The other three templates declare no LINK parameter; handing one an extra
        context key would put a value into Meta's positional body it never approved."""
        svc = _sender()
        await svc.send_customer_milestone(
            USER, CASE, AvailableTemplate.WHATSAPP_INSPECTION_COMPLETE
        )
        assert MessageContext.LINK not in _sent(messages)[0].kwargs["context"]


class TestFailureIsAbsorbed:
    async def test_a_raising_transport_never_escapes(self, messages):
        messages.send_whatsapp_milestone.side_effect = RuntimeError("Meta is down")
        svc = _sender()
        await svc.send_customer_milestone(
            USER, CASE, AvailableTemplate.WHATSAPP_PAYMENT_CONFIRMED
        )  # no exception

    async def test_outbound_disabled_sends_nothing(self, messages, monkeypatch):
        from main.app.config import settings as settings_module

        monkeypatch.setattr(settings_module.settings, "ENABLE_OUT_MESSAGING", False)
        svc = _sender()
        await svc.send_customer_milestone(
            USER, CASE, AvailableTemplate.WHATSAPP_PAYMENT_CONFIRMED
        )
        assert _sent(messages) == []

    async def test_a_missing_verification_sends_nothing(self, messages):
        """Every milestone names a case. If the row has gone, there is no reference to
        send and no reason to guess one."""
        svc = _sender()
        svc._verification_repo.get_model = AsyncMock(return_value=None)
        await svc.send_customer_milestone(
            USER, CASE, AvailableTemplate.WHATSAPP_PAYMENT_CONFIRMED
        )
        assert _sent(messages) == []


class TestStatusLabel:
    def test_the_delegate_reads_the_same_words_as_the_dashboard(self):
        """The §7.3.2 projection's stage names are the channel's internal vocabulary. A
        delegate is a person, so they get `tracking/labels.py` — what the buyer sees."""
        label = status_label_for(_verification(VerificationStatus.IN_PROGRESS))
        assert label
        assert label != VerificationStatus.IN_PROGRESS.value
