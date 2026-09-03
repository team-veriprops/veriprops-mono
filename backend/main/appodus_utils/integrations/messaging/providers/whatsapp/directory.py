"""Reading template approval status back from Meta (PRD §7.7, WA-15/WA-41).

Submitting a template is not the same as being able to send it. Meta reviews each one and
the answer arrives asynchronously — sometimes days later, sometimes as a rejection with a
reason. §7.11 makes "all §7.7 templates approved" a launch gate precisely because that lag
sits on the critical path, so the answer has to be visible in the app rather than in
somebody's inbox.

This is a **read** facade, deliberately separate from the send providers: asking what Meta
knows is not sending, and the two have different failure modes. It follows the same
exclusivity rule as the send router (D43) — `WHATSAPP_PROVIDER` picks one, there is no
fallback between them, and the stub is what CI and e2e run so **no automated run ever
reaches Meta**.
"""
from __future__ import annotations

import abc
from typing import List, Optional

from httpx import AsyncClient
from kink import di, inject

from main.app.config.settings import settings
from main.appodus_utils import Object
from main.appodus_utils.config.settings import WhatsAppProvider
from main.appodus_utils.integrations.exception.exceptions import (
    IntegrationAuthenticationException,
    IntegrationException,
)
from main.appodus_utils.integrations.messaging.templating.whatsapp_templates import (
    declared_templates,
)

logger = di["logger"]

# Meta's review states, verbatim (GET /{waba-id}/message_templates). Kept as strings
# rather than an enum here because it is *their* vocabulary arriving over the wire; the
# app-side enum that stores it lives with the registry entity.
META_STATUS_APPROVED = "APPROVED"
META_STATUS_PENDING = "PENDING"


class RemoteTemplate(Object):
    """One template as Meta currently sees it."""

    name: str
    status: str
    category: Optional[str] = None
    language: Optional[str] = None
    remote_id: Optional[str] = None
    rejection_reason: Optional[str] = None


class IWhatsAppTemplateDirectory(abc.ABC):
    """What Meta knows about our templates."""

    @abc.abstractmethod
    async def list_templates(self) -> List[RemoteTemplate]:
        """Every template registered on the business account."""
        raise NotImplementedError


class StubTemplateDirectory(IWhatsAppTemplateDirectory):
    """Deterministic stand-in: reports the declared set as approved.

    Approved rather than pending on purpose — the stub exists so the whole channel is
    exercisable without Meta, and a permanently-pending registry would make every
    downstream assertion test the waiting rather than the wiring.
    """

    async def list_templates(self) -> List[RemoteTemplate]:
        return [
            RemoteTemplate(
                name=declaration.name,
                status=META_STATUS_APPROVED,
                category=declaration.category.value,
                language=declaration.language,
                remote_id=f"stub-{declaration.name}",
            )
            for declaration in declared_templates()
        ]


@inject
class MetaTemplateDirectory(IWhatsAppTemplateDirectory):
    """The live Cloud API: ``GET /{waba_id}/message_templates``."""

    def __init__(self):
        self.client = di[AsyncClient]

    async def list_templates(self) -> List[RemoteTemplate]:
        waba_id = settings.WHATSAPP_BUSINESS_ACCOUNT_ID
        url = f"{settings.WHATSAPP_API_URL}/{waba_id}/message_templates"
        response = await self.client.get(
            url,
            params={"limit": 100, "fields": "id,name,status,category,language,rejected_reason"},
            headers={"Authorization": f"Bearer {settings.WHATSAPP_BUSINESS_ACCESS_TOKEN}"},
        )

        if response.status_code in (401, 403):
            raise IntegrationAuthenticationException(
                "WhatsApp template directory rejected our credentials — check the "
                "business account id and access token."
            )
        if response.status_code >= 400:
            # The body carries Meta's error object; log the status only. A directory
            # response can name every template on the account, which is business data.
            raise IntegrationException(
                f"WhatsApp template directory returned HTTP {response.status_code}"
            )

        return [
            RemoteTemplate(
                name=row.get("name", ""),
                status=row.get("status", ""),
                category=row.get("category"),
                language=row.get("language"),
                remote_id=str(row.get("id")) if row.get("id") else None,
                rejection_reason=row.get("rejected_reason"),
            )
            for row in response.json().get("data", [])
        ]


def whatsapp_template_directory() -> IWhatsAppTemplateDirectory:
    """The directory for the configured transport.

    Exclusive, like the send rules: production reaching the stub, or a test run reaching
    Meta, are both configuration failures the startup policy already refuses.
    """
    if settings.WHATSAPP_PROVIDER == WhatsAppProvider.META:
        return di[MetaTemplateDirectory]
    return StubTemplateDirectory()


# ─── Number health (§7.10, §7.11; D81) ────────────────────────────
#
# The same posture as the template directory above, for the other thing Meta knows about
# us: how healthy it considers our number. §7.10 counts the quality rating as the channel's
# platform-dependency early warning — property is a scam-saturated category under
# aggressive automated enforcement, and the rating is the signal that arrives *before* the
# number is throttled or banned. A separate interface rather than a method on the template
# directory: one answers "may we send this template", the other "may we send at all", and
# the two have different endpoints and different failure consequences.


class RemoteNumberHealth(Object):
    """Our business number as Meta currently sees it."""

    quality_rating: str
    messaging_limit_tier: Optional[str] = None
    verified_name: Optional[str] = None


class IWhatsAppNumberDirectory(abc.ABC):
    """What Meta thinks of the number we send from."""

    @abc.abstractmethod
    async def fetch_number_health(self) -> RemoteNumberHealth:
        raise NotImplementedError


class StubNumberDirectory(IWhatsAppNumberDirectory):
    """Deterministic stand-in: a healthy number.

    `GREEN` rather than `UNKNOWN` for the same reason the stub template directory reports
    APPROVED — the stub exists so the channel is fully exercisable without Meta, and a
    permanently-unknown rating would make every assertion downstream test the absence of a
    sync rather than the wiring. The admin surface labels the source, so nobody mistakes
    this for Meta's opinion.
    """

    async def fetch_number_health(self) -> RemoteNumberHealth:
        return RemoteNumberHealth(
            quality_rating="GREEN",
            messaging_limit_tier="TIER_1K",
            verified_name=settings.BRAND_DISPLAY_NAME,
        )


@inject
class MetaNumberDirectory(IWhatsAppNumberDirectory):
    """The live Cloud API: ``GET /{phone_number_id}?fields=quality_rating,…``."""

    def __init__(self):
        self.client = di[AsyncClient]

    async def fetch_number_health(self) -> RemoteNumberHealth:
        phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
        url = f"{settings.WHATSAPP_API_URL}/{phone_number_id}"
        response = await self.client.get(
            url,
            params={"fields": "quality_rating,messaging_limit_tier,verified_name"},
            headers={"Authorization": f"Bearer {settings.WHATSAPP_BUSINESS_ACCESS_TOKEN}"},
        )

        if response.status_code in (401, 403):
            raise IntegrationAuthenticationException(
                "WhatsApp number directory rejected our credentials — check the phone "
                "number id and access token."
            )
        if response.status_code >= 400:
            raise IntegrationException(
                f"WhatsApp number directory returned HTTP {response.status_code}"
            )

        body = response.json()
        return RemoteNumberHealth(
            quality_rating=str(body.get("quality_rating") or "UNKNOWN"),
            messaging_limit_tier=body.get("messaging_limit_tier"),
            verified_name=body.get("verified_name"),
        )


def whatsapp_number_directory() -> IWhatsAppNumberDirectory:
    """The number directory for the configured transport (exclusive, like the send rules)."""
    if settings.WHATSAPP_PROVIDER == WhatsAppProvider.META:
        return di[MetaNumberDirectory]
    return StubNumberDirectory()
