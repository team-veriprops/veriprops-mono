"""Meta number-health sync (PRD §26.10, §26.11; D81).

Keeps the app's picture of what Meta thinks of our sending number, in exactly the posture
the §26.7 template registry established (D59a): **Meta owns the value, we store what it last
told us alongside when it told us, and nothing in the send path ever reads it.**

That last clause is the important one. A quality rating is an early warning for a person,
not a gate for the code: blocking sends on a RED rating would take the channel down on the
strength of a number we cannot verify and did not compute, and blocking on a *stale* rating
would take it down because a Graph call timed out. So a failed sync is recorded on the row
and shown as a sync age; the channel carries on regardless.
"""
from __future__ import annotations

from logging import Logger
from typing import Optional

from kink import di, inject

from main.app.config.settings import settings
from main.app.domain.channel.whatsapp.analytics.models import (
    CreateWhatsAppNumberHealthDto,
    WhatsAppNumberHealth,
    WhatsAppQualityRating,
)
from main.app.domain.channel.whatsapp.analytics.repo import WhatsAppNumberHealthRepo
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.integrations.messaging.providers.whatsapp.directory import (
    whatsapp_number_directory,
)

logger: Logger = di["logger"]

# The number we send from is a single configured identity, so "which row" never needs
# asking. Falling back to a literal keeps the service usable before the id is configured —
# the row then records that we have never successfully synced, which is the truth.
_UNCONFIGURED = "unconfigured"


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class WhatsAppNumberHealthService:
    def __init__(self, whatsapp_number_health_repo: WhatsAppNumberHealthRepo):
        self._health = whatsapp_number_health_repo

    async def current(self) -> Optional[WhatsAppNumberHealth]:
        """What we last heard, or ``None`` before the first sync ever ran."""
        return await self._health.latest()

    async def sync(self) -> WhatsAppNumberHealth:
        """Ask Meta and record the answer — including the answer "we could not ask".

        Never raises. The caller is an admin refreshing a dashboard tile; an exception
        there would turn a Graph hiccup into a 500 on the analytics page, and the honest
        rendering is "here is what we last knew, and we have not been able to ask since".
        """
        phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID or _UNCONFIGURED
        row = await self._health.get_by_phone_number_id(phone_number_id)
        if row is None:
            row = await self._health.create_return_model(
                CreateWhatsAppNumberHealthDto(phone_number_id=phone_number_id)
            )

        try:
            remote = await whatsapp_number_directory().fetch_number_health()
        except Exception as failure:  # noqa: BLE001 — recorded, never raised
            logger.warning(
                "WhatsApp number-health sync failed (§26.10) — keeping the last known "
                "rating and recording the failure: %s",
                failure,
            )
            # The rating is deliberately left as it was. Downgrading it to UNKNOWN on a
            # failed call would make a network blip look like Meta had withdrawn its
            # verdict, which is a different and more alarming thing.
            return self._health.apply(
                row,
                quality_rating=row.quality_rating,
                messaging_limit_tier=row.messaging_limit_tier,
                synced_at=None,
                sync_error=str(failure)[:255],
            )

        return self._health.apply(
            row,
            quality_rating=_known_rating(remote.quality_rating),
            messaging_limit_tier=remote.messaging_limit_tier,
            synced_at=Utils.datetime_now(),
            sync_error=None,
        )


def _known_rating(raw: Optional[str]) -> str:
    """Meta's rating, or ``UNKNOWN`` for anything we do not recognise.

    Meta has used other spellings over the API's life, and a value we cannot read must not
    be stored as if it were a verdict — least of all be mistaken for GREEN.
    """
    try:
        return WhatsAppQualityRating(str(raw or "").strip().upper()).value
    except ValueError:
        return WhatsAppQualityRating.UNKNOWN.value
