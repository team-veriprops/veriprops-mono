"""Portal dashboard summary service — aggregates verification counts and unread reports."""
from __future__ import annotations

import json
from typing import List, Optional

from kink import inject

from main.app.domain.verification.models import Verification
from main.app.domain.verification.portal.models import (
    AbandonedVerificationSummaryDto,
    DashboardSummaryDto,
)
from main.app.domain.verification.property.repo import PropertyRepo
from main.app.domain.verification.repo import VerificationRepo
from main.app.domain.verification.report.repo import ReportViewRepo
from main.appodus_utils.decorators.transactional import transactional

_ACTIVE_STATUSES = {"PAID", "PAYMENT_PENDING", "IN_PROGRESS", "UNDER_REVIEW"}


def _parse_pricing(verification: Verification) -> tuple[Optional[int], Optional[str]]:
    if not verification.pricing_snapshot:
        return None, None
    try:
        data = json.loads(verification.pricing_snapshot)
        total = data.get("totalAmountMinor") or data.get("total_amount_minor")
        currency = data.get("currency")
        return (int(total) if total is not None else None), currency
    except (json.JSONDecodeError, ValueError, TypeError):
        return None, None


@inject
class PortalDashboardService:
    def __init__(
        self,
        ver_repo: VerificationRepo,
        prop_repo: PropertyRepo,
        report_view_repo: ReportViewRepo,
    ) -> None:
        self._ver_repo = ver_repo
        self._prop_repo = prop_repo
        self._report_view_repo = report_view_repo

    @transactional()
    async def get_summary(self, customer_id: str) -> DashboardSummaryDto:
        counts = await self._ver_repo.count_by_status_for_customer(customer_id)
        total = sum(counts.values())
        active = sum(counts.get(s, 0) for s in _ACTIVE_STATUSES)
        completed = counts.get("COMPLETED", 0)

        abandoned_rows = await self._ver_repo.list_abandoned_for_customer(customer_id)
        abandoned_dtos = await self._build_abandoned_dtos(abandoned_rows)

        unread_report_count = 0
        if completed > 0:
            completed_vids = await self._ver_repo.list_completed_vids_for_customer(customer_id)
            unread_report_count = await self._report_view_repo.count_unacknowledged_for_customer(
                customer_id, completed_vids
            )

        return DashboardSummaryDto(
            total=total,
            active=active,
            completed=completed,
            unread_report_count=unread_report_count,
            abandoned=abandoned_dtos,
        )

    async def _build_abandoned_dtos(
        self, rows: List[Verification]
    ) -> List[AbandonedVerificationSummaryDto]:
        dtos: List[AbandonedVerificationSummaryDto] = []
        for row in rows:
            prop_state: Optional[str] = None
            prop_lga: Optional[str] = None
            prop_address: Optional[str] = None
            if row.property_id:
                prop = await self._prop_repo.get_model(str(row.property_id))
                if prop:
                    prop_state = prop.state
                    prop_lga = prop.lga
                    prop_address = prop.address_line
            total_amount_minor, currency = _parse_pricing(row)
            dtos.append(
                AbandonedVerificationSummaryDto(
                    id=str(row.id),
                    vid=row.vid,
                    tier=row.tier,
                    status=row.status,
                    property_state=prop_state,
                    property_lga=prop_lga,
                    property_address=prop_address,
                    total_amount_minor=total_amount_minor,
                    currency=currency,
                    date_updated=row.date_updated,
                    date_created=row.date_created,
                )
            )
        return dtos
