"""WhatsApp template rendering (PRD §7, D46).

This path was unreachable until account linking needed it, and it was broken in three
independent ways when it was first exercised: the render call was never awaited, it
passed the wrong keyword to `render_model`, and it fed a plain-text template to a JSON
parser. Nothing caught it because nothing had ever sent a WhatsApp template message.

So these tests render every committed WhatsApp template for real. A template that does
not render is a runtime 500 the moment its notification fires — which is exactly how the
OTP that links a customer's number would have failed.
"""
from pathlib import Path

import pytest
from kink import di

# Imported first, and only for its side effect: `channel_sender` reaches back into the
# app's message domain, so importing it cold from a test leaves that module half-built.
# The domain package is the aggregation point that warms the graph (the sibling messaging
# tests get this for free by importing a domain model at the top).
from main.app import domain as _domain  # noqa: F401
from main.appodus_utils.db.types.phone import PhoneNumber
from main.appodus_utils.integrations.messaging.channel_sender import WhatsAppRequestBuilder
from main.appodus_utils.integrations.messaging.models import (
    MessageChannel,
    MessageRequestRecipient,
)
from main.appodus_utils.integrations.messaging.templating.model_template_service import (
    ModelTemplateService,
)
from main.appodus_utils.integrations.messaging.templating.models import AvailableTemplate

# Every context key any WhatsApp template uses. Jinja renders an unknown variable as an
# empty string rather than failing, so a superset is safe and keeps this list from
# needing an edit per template.
_CONTEXT = {
    "BRAND": "Veriprops",
    "FIRST_NAME": "Ada",
    "OTP": "654123",
    "VALIDITY": "10 minutes",
    "BRAND_SUPPORT_EMAIL": "support@veriprops.ng",
    "BRAND_SUPPORT_PHONE": "+2349167624347",
}

# backend/test/unit/appodus_utils/integrations/messaging/<this file> -> backend/ is parents[5].
_TEMPLATE_DIR = (
    Path(__file__).resolve().parents[5]
    / "main" / "appodus_utils" / "integrations" / "messaging" / "templates"
    / MessageChannel.WHATSAPP.value
)


def _committed_whatsapp_templates() -> list[AvailableTemplate]:
    slugs = {p.stem for p in _TEMPLATE_DIR.glob("*.jinja2")}
    templates = [t for t in AvailableTemplate if t.value in slugs]
    # An empty list would make the parametrized tests silently skip — the exact way this
    # whole path stayed broken in the first place.
    assert templates, f"no WhatsApp templates found under {_TEMPLATE_DIR}"
    return templates


@pytest.mark.parametrize(
    "template", _committed_whatsapp_templates(), ids=lambda t: t.value
)
async def test_every_committed_whatsapp_template_renders(template: AvailableTemplate):
    payload = await di[ModelTemplateService].render_whatsapp_payload(template, _CONTEXT)
    assert payload.text, f"{template.value} rendered an empty body"


@pytest.mark.parametrize(
    "template", _committed_whatsapp_templates(), ids=lambda t: t.value
)
async def test_no_whatsapp_template_carries_an_email_subject_line(template: AvailableTemplate):
    # WhatsApp has no subject. A template copied from its email sibling ships the header
    # as the first line of the message, which reads as a bug to the customer.
    payload = await di[ModelTemplateService].render_whatsapp_payload(template, _CONTEXT)
    assert not payload.text.lower().startswith("subject:")


class TestOtpAuthTemplate:
    """The §7.4.4 linking code — the one template an account depends on."""

    async def test_carries_the_code_and_its_validity(self):
        payload = await di[ModelTemplateService].render_whatsapp_payload(
            AvailableTemplate.WHATSAPP_OTP_AUTH, _CONTEXT
        )
        assert "654123" in payload.text
        assert "10 minutes" in payload.text

    async def test_warns_that_veriprops_will_never_ask_for_it(self):
        # §7.1.2 anti-impersonation: the standing defence against someone phoning a
        # customer to ask for the code they just received.
        payload = await di[ModelTemplateService].render_whatsapp_payload(
            AvailableTemplate.WHATSAPP_OTP_AUTH, _CONTEXT
        )
        assert "never ask" in payload.text.lower()

    async def test_names_the_brand_so_the_message_is_attributable(self):
        payload = await di[ModelTemplateService].render_whatsapp_payload(
            AvailableTemplate.WHATSAPP_OTP_AUTH, _CONTEXT
        )
        assert "Veriprops" in payload.text


async def test_a_missing_template_fails_loudly_rather_than_sending_an_empty_message():
    from main.appodus_utils.exception.exceptions import TemplateRenderingException

    with pytest.raises(TemplateRenderingException):
        await di[ModelTemplateService].render_whatsapp_payload(
            # Registered for email, with no WhatsApp sibling.
            AvailableTemplate.PASSWORD_RESET_SUCCESS, _CONTEXT
        )


def test_the_whatsapp_channel_directory_is_where_the_renderer_looks():
    # The renderer builds `<channel>/<slug>.jinja2`; a template dropped elsewhere is
    # invisible to it, and the failure only shows at send time.
    assert _TEMPLATE_DIR.name == MessageChannel.WHATSAPP.value


class TestWhatsAppRequestBuilder:
    """The layer above the template — where the send was actually dying.

    `MessageRequestRecipient.phone_digits` did not exist, so **every** WhatsApp send in
    the system failed at build time. `_build_requests_for_channels` catches per-channel
    build errors and logs them, so a send whose only channel is WhatsApp raised a generic
    RuntimeError two frames up, and one whose channel list also held email or SMS
    degraded to a "partial failure" warning nobody read. Both look like success from the
    caller's side.
    """

    async def test_builds_a_request_addressed_in_metas_digits_only_form(self):
        builder = WhatsAppRequestBuilder(di[ModelTemplateService])
        request = await builder.build_request(
            recipient=MessageRequestRecipient(phone=PhoneNumber.from_e164("+2348012345678")),
            template=AvailableTemplate.WHATSAPP_OTP_AUTH,
            context=_CONTEXT,
        )
        # Digits only: a leading '+' is rejected by the Cloud API and by the stub.
        assert request.to.recipient == "2348012345678"
        assert request.channel == MessageChannel.WHATSAPP
        assert "654123" in request.payload.text

    def test_phone_digits_strips_the_e164_plus(self):
        recipient = MessageRequestRecipient(phone=PhoneNumber.from_e164("+2348012345678"))
        assert recipient.phone_digits == "2348012345678"

    def test_phone_digits_is_empty_for_a_recipient_with_no_number(self):
        assert MessageRequestRecipient(email="ada@example.com").phone_digits == ""

    async def test_refuses_to_build_without_a_number(self):
        builder = WhatsAppRequestBuilder(di[ModelTemplateService])
        with pytest.raises(ValueError):
            await builder.build_request(
                recipient=MessageRequestRecipient(email="ada@example.com"),
                template=AvailableTemplate.WHATSAPP_OTP_AUTH,
                context=_CONTEXT,
            )
