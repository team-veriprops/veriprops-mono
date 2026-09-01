"""The §7.7 Meta template declarations.

Meta will not deliver a business-initiated WhatsApp message as free text. Outside the
24-hour service window — which is where every message in this table lives, because each
one is something *we* decided to say — the Cloud API accepts only a pre-approved
**template**, addressed by name, with its variables supplied positionally.

That makes this table the contract between three things that must agree exactly: the copy
submitted to Meta for approval, the Jinja body a customer reads in the thread, and the
code that fills the variables. It is **code-owned for that reason** (D59a). A registry
whose parameter list could be edited without touching the sender would be describing
something the app does not do — and the failure would only appear as a rejected send in
production.

What lives here vs elsewhere:

* **Here**: the Meta template name, its category, its language, and the *order* of its
  parameters. Order is the whole game — Meta's body parameters are positional, so a
  reordered list silently sends the customer someone else's numbers.
* **In the database** (`app/domain/channel/whatsapp/template/`): approval status, synced
  from Meta. That is Meta's answer about a template, not a fact about our code.
* **In `templates/whatsapp/<slug>.jinja2`**: the body copy itself.

§7.7 calls template approval "on the critical path", so all seven are declared now even
though only `otp_auth` has a sender yet — declaring one is what lets it be submitted, and
the admin registry is what tracks the answer coming back.
"""
from __future__ import annotations

import enum
from typing import Dict, List, Optional, Sequence

from main.appodus_utils.integrations.messaging.models import MessageContext
from main.appodus_utils.integrations.messaging.templating.models import AvailableTemplate


class MetaTemplateCategory(str, enum.Enum):
    """Meta's template categories. Category drives pricing and review strictness."""

    AUTHENTICATION = "AUTHENTICATION"
    UTILITY = "UTILITY"
    MARKETING = "MARKETING"


class MetaTemplateButton(str, enum.Enum):
    """The OTP button an authentication template carries.

    Meta **mandates** an OTP button on authentication templates — copy-code or one-tap
    autofill — and a send must then include a matching `button` component alongside the
    body. Omitting it is not a cosmetic difference: the message is rejected.

    Both kinds are sent identically. The button is created as a URL button, so the send
    uses `sub_type: "url"` at `index: "0"` and passes the verification code as its single
    parameter; the difference between copy-code and one-tap is in how the *client* handles
    the tap, not in what we transmit.
    """

    # Utility templates carry no OTP button.
    NONE = "NONE"
    COPY_CODE = "COPY_CODE"
    ONE_TAP = "ONE_TAP"

    @property
    def is_otp_button(self) -> bool:
        return self is not MetaTemplateButton.NONE


class MetaTemplate:
    """One §7.7 template: what Meta knows it as, and how we fill it."""

    def __init__(
        self,
        template: AvailableTemplate,
        category: MetaTemplateCategory,
        parameters: Sequence[MessageContext],
        language: str = "en",
        button: MetaTemplateButton = MetaTemplateButton.NONE,
    ):
        self.template = template
        self.category = category
        # Ordered: index 0 becomes Meta's body parameter "1". Never reorder without
        # re-submitting the template — the customer would get the right values in the
        # wrong sentence.
        self.parameters: List[MessageContext] = list(parameters)
        self.language = language
        self.button = button

    @property
    def name(self) -> str:
        """The Meta template name. The `AvailableTemplate` slug **is** the Meta name, so
        the registry, the Jinja file, and the wire cannot drift apart."""
        return self.template.value

    def positional_variables(self, context: Dict) -> Dict[str, str]:
        """Meta's positional body parameters, built from *context* in declared order.

        Keys are `"1"`, `"2"`, … because that is what the Cloud API expects. A parameter
        the context does not carry becomes an empty string rather than raising: a missing
        value should degrade one placeholder, not drop a customer's OTP entirely.
        """
        return {
            str(position): str(context.get(parameter, ""))
            for position, parameter in enumerate(self.parameters, start=1)
        }

    def button_parameter(self, context: Dict) -> Optional[str]:
        """The value Meta's OTP button carries — the code itself.

        The button repeats the code so the client can copy or autofill it, which is why
        the *first* declared parameter feeds it: on an authentication template that is the
        one-time password by construction.
        """
        if not self.button.is_otp_button or not self.parameters:
            return None
        return str(context.get(self.parameters[0], ""))


# PRD §7.7. Marketing templates: none at v1, by decision — drafted only when a consented
# campaign is planned (P1 audience).
_DECLARED: Sequence[MetaTemplate] = (
    # E1 linking flows (§7.4.4). The only one with a live sender today, and the only
    # AUTHENTICATION template — hence the mandatory OTP button.
    MetaTemplate(
        AvailableTemplate.WHATSAPP_OTP_AUTH,
        MetaTemplateCategory.AUTHENTICATION,
        parameters=(MessageContext.OTP, MessageContext.VALIDITY),
        button=MetaTemplateButton.COPY_CODE,
    ),
    # Milestone templates (§7.6.2) — opt-in, fired by state events. Senders land in S8.
    MetaTemplate(
        AvailableTemplate.WHATSAPP_PAYMENT_CONFIRMED,
        MetaTemplateCategory.UTILITY,
        parameters=(MessageContext.SHARE_VID,),
    ),
    MetaTemplate(
        AvailableTemplate.WHATSAPP_VERIFICATION_STARTED,
        MetaTemplateCategory.UTILITY,
        parameters=(MessageContext.SHARE_VID,),
    ),
    MetaTemplate(
        AvailableTemplate.WHATSAPP_INSPECTION_COMPLETE,
        MetaTemplateCategory.UTILITY,
        parameters=(MessageContext.SHARE_VID,),
    ),
    # Report delivery (§7.6.2, Decision B) — the link lands in the authenticated portal.
    MetaTemplate(
        AvailableTemplate.WHATSAPP_REPORT_READY,
        MetaTemplateCategory.UTILITY,
        parameters=(MessageContext.SHARE_VID, MessageContext.LINK),
    ),
    # Agent reply outside Meta's 24-hour service window (§7.7, WA-41). Sender lands in S7.
    MetaTemplate(
        AvailableTemplate.WHATSAPP_WINDOW_REOPEN,
        MetaTemplateCategory.UTILITY,
        parameters=(MessageContext.FIRST_NAME,),
    ),
    # Delegate milestone delivery (§7.4.5, O2). Sender lands in S9.
    MetaTemplate(
        AvailableTemplate.WHATSAPP_DELEGATE_STATUS,
        MetaTemplateCategory.UTILITY,
        parameters=(MessageContext.SHARE_VID, MessageContext.VERIFICATION_NEW_STATUS),
    ),
)

_BY_TEMPLATE: Dict[AvailableTemplate, MetaTemplate] = {d.template: d for d in _DECLARED}


def declared_templates() -> List[MetaTemplate]:
    """Every §7.7 template, in declaration order (what the admin registry lists)."""
    return list(_DECLARED)


def meta_template_for(template: AvailableTemplate) -> Optional[MetaTemplate]:
    """The declaration for *template*, or ``None`` if it is not a §7.7 template.

    ``None`` is the ordinary case for in-conversation copy: a bot reply is inside the
    service window by construction (the customer just messaged), so it goes as free text
    and needs no approved template.
    """
    return _BY_TEMPLATE.get(template)
