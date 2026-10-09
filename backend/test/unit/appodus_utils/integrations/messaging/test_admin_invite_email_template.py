"""The admin-invitation email (PRD §9.1).

The invitee is greeted by their own name and told who invited them. The template once used
`FULL_NAME` for the inviter and `FIRST_NAME` for the invitee, which the sender filled from one
person, so the email read as the invitee inviting themselves.
"""
from kink import di

from main.app import domain as _domain  # noqa: F401  — warms the messaging import graph
from main.appodus_utils.integrations.messaging.models import MessageChannel, MessageContext
from main.appodus_utils.integrations.messaging.templating.models import AvailableTemplate
from main.appodus_utils.integrations.messaging.templating.service import TemplateService

_CONTEXT = {
    MessageContext.BRAND: "Veriprops",
    MessageContext.FIRST_NAME: "Ada",
    MessageContext.INVITER_NAME: "Sam Super",
    MessageContext.ADMIN_ROLE: "Finance",
    MessageContext.LINK: "https://veriprops.ng/auth/admin-invite/tok123",
    MessageContext.VALIDITY: "72 hours",
}


async def _render(context: dict) -> str:
    return await di[TemplateService].render_message(
        MessageChannel.EMAIL, AvailableTemplate.NEW_ADMIN_USER_INVITE, context,
    )


async def test_subject_names_the_inviter():
    subject = (await _render(_CONTEXT)).splitlines()[0]
    assert subject.startswith("Subject:")
    assert "Sam Super" in subject
    assert "Veriprops" in subject


async def test_greets_the_invitee_and_names_the_inviter_and_role():
    body = await _render(_CONTEXT)
    assert "Hello Ada" in body
    assert "Sam Super" in body
    assert "Finance" in body


async def test_carries_the_link_and_its_validity():
    body = await _render(_CONTEXT)
    assert "https://veriprops.ng/auth/admin-invite/tok123" in body
    assert "72 hours" in body


async def test_an_unnamed_invitee_is_greeted_without_a_placeholder():
    body = await _render({**_CONTEXT, MessageContext.FIRST_NAME: None})
    assert "None" not in body
    assert "Hello," in body
