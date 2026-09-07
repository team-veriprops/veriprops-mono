"""Channel-analytics data access (PRD §26.10, D80).

Two shapes only, because §26.10 asks two kinds of question: "how many of this happened in
this window?" and "how many of each, broken down by one column?". Both are SQL-side
aggregations rather than row pulls — a fact table grows with traffic rather than with
customers, so the `analytics_snapshot()` habit of loading everything and counting in Python
would be the one place in the codebase where that stops being fine.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence, Type

from kink import inject
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.channel.whatsapp.analytics.models import (
    CreateWhatsAppChannelEventDto,
    CreateWhatsAppNumberHealthDto,
    QueryWhatsAppChannelEventDto,
    QueryWhatsAppNumberHealthDto,
    SearchWhatsAppChannelEventDto,
    SearchWhatsAppNumberHealthDto,
    UpdateWhatsAppChannelEventDto,
    UpdateWhatsAppNumberHealthDto,
    WhatsAppChannelEvent,
    WhatsAppChannelEventType,
    WhatsAppNumberHealth,
)
from main.appodus_utils.db.repo import GenericRepo

# What an enquiry with no `[ref: …]` marker is counted as. Someone who saved the number or
# was given it by a friend is real channel demand; bucketing them keeps the page-code
# breakdown honest about how much of the traffic the widget actually explains.
UNATTRIBUTED_PAGE_CODE = "direct"


@inject
class WhatsAppChannelEventRepo(
    GenericRepo[
        WhatsAppChannelEvent,
        CreateWhatsAppChannelEventDto,
        UpdateWhatsAppChannelEventDto,
        QueryWhatsAppChannelEventDto,
        SearchWhatsAppChannelEventDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[WhatsAppChannelEvent] = WhatsAppChannelEvent,
        query_dto: Type[QueryWhatsAppChannelEventDto] = QueryWhatsAppChannelEventDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def count_by_type(
        self, event_types: Sequence[WhatsAppChannelEventType], since: datetime
    ) -> dict[str, int]:
        """How many of each requested type occurred since *since*.

        One grouped query rather than one per type: a §26.10 rate is always a pair of these
        counts, and issuing them separately would let the two halves be read at different
        moments and produce a ratio above 1.
        """
        stmt = (
            select(WhatsAppChannelEvent.event_type, func.count())
            .where(
                and_(
                    WhatsAppChannelEvent.deleted.is_(False),
                    WhatsAppChannelEvent.occurred_at >= since,
                    WhatsAppChannelEvent.event_type.in_(
                        [event_type.value for event_type in event_types]
                    ),
                )
            )
            .group_by(WhatsAppChannelEvent.event_type)
        )
        counted = {row[0]: int(row[1]) for row in (await self._session.execute(stmt)).all()}
        # Absent means zero, and every caller wants a total key set — a missing key would
        # otherwise become a KeyError on the quietest day the channel has.
        return {event_type.value: counted.get(event_type.value, 0) for event_type in event_types}

    async def count_by_page_code(self, since: datetime) -> dict[str, int]:
        """§26.10's WhatsApp-attributed enquiries, by widget page code.

        Enquiries with no code are counted under `direct`: someone who saved the number or
        was given it by a friend is real channel demand, and dropping them would make the
        widget look like the only source of traffic.

        The bucketing happens in Python rather than as a SQL `coalesce`. Grouping by an
        expression containing a literal makes SQLAlchemy bind that literal once for the
        select list and again for the `GROUP BY`, and Postgres then sees two different
        expressions and rejects the query — so the NULL group is named here instead.
        """
        stmt = (
            select(WhatsAppChannelEvent.page_code, func.count())
            .where(
                and_(
                    WhatsAppChannelEvent.deleted.is_(False),
                    WhatsAppChannelEvent.occurred_at >= since,
                    WhatsAppChannelEvent.event_type
                    == WhatsAppChannelEventType.ENQUIRY.value,
                )
            )
            .group_by(WhatsAppChannelEvent.page_code)
        )
        counted: dict[str, int] = {}
        for page_code, total in (await self._session.execute(stmt)).all():
            label = page_code or UNATTRIBUTED_PAGE_CODE
            counted[label] = counted.get(label, 0) + int(total)
        return counted

    async def count_by_escalation_reason(self, since: datetime) -> dict[str, int]:
        """§26.10's escalation reasons — the half of the metric that says what to build next."""
        stmt = (
            select(WhatsAppChannelEvent.reason, func.count())
            .where(
                and_(
                    WhatsAppChannelEvent.deleted.is_(False),
                    WhatsAppChannelEvent.occurred_at >= since,
                    WhatsAppChannelEvent.event_type
                    == WhatsAppChannelEventType.ESCALATED.value,
                    WhatsAppChannelEvent.reason.is_not(None),
                )
            )
            .group_by(WhatsAppChannelEvent.reason)
        )
        return {row[0]: int(row[1]) for row in (await self._session.execute(stmt)).all()}

    async def has_events_for_verification(self, verification_id: str) -> bool:
        """Did this verification come through the WhatsApp channel?

        Answered from the facts rather than from a column on `verifications` (D80): the
        channel's own table already knows which cases it produced, and an origin column on
        the shared verification row would be a second thing to keep true.
        """
        stmt = select(func.count()).select_from(WhatsAppChannelEvent).where(
            and_(
                WhatsAppChannelEvent.deleted.is_(False),
                WhatsAppChannelEvent.verification_id == verification_id,
            )
        )
        return bool(await self._session.scalar(stmt))


@inject
class WhatsAppNumberHealthRepo(
    GenericRepo[
        WhatsAppNumberHealth,
        CreateWhatsAppNumberHealthDto,
        UpdateWhatsAppNumberHealthDto,
        QueryWhatsAppNumberHealthDto,
        SearchWhatsAppNumberHealthDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[WhatsAppNumberHealth] = WhatsAppNumberHealth,
        query_dto: Type[QueryWhatsAppNumberHealthDto] = QueryWhatsAppNumberHealthDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_by_phone_number_id(
        self, phone_number_id: str
    ) -> Optional[WhatsAppNumberHealth]:
        stmt = select(WhatsAppNumberHealth).where(
            and_(
                WhatsAppNumberHealth.deleted.is_(False),
                WhatsAppNumberHealth.phone_number_id == phone_number_id,
            )
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def latest(self) -> Optional[WhatsAppNumberHealth]:
        """The one row the analytics surface renders, whichever number it is for."""
        stmt = (
            select(WhatsAppNumberHealth)
            .where(WhatsAppNumberHealth.deleted.is_(False))
            .order_by(WhatsAppNumberHealth.date_created.desc())
        )
        return (await self._session.execute(stmt)).scalars().first()

    def apply(
        self,
        health: WhatsAppNumberHealth,
        *,
        quality_rating: str,
        messaging_limit_tier: Optional[str],
        synced_at: Optional[datetime],
        sync_error: Optional[str],
    ) -> WhatsAppNumberHealth:
        """Record one sync result on the attached row.

        Mutates the attached object rather than going through the generic update path,
        which stringifies datetimes before binding — asyncpg then refuses the string for a
        timestamp column (the same reason `WhatsAppConsentRepo.apply` exists).
        """
        health.quality_rating = quality_rating
        health.messaging_limit_tier = messaging_limit_tier
        health.sync_error = sync_error
        if synced_at is not None:
            health.last_synced_at = synced_at
        self._session.add(health)
        return health
