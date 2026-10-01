"""Finance summary DTO (PRD §18.1): the tiles on the Finance landing page."""
from __future__ import annotations

from typing import Dict

from main.appodus_utils import Object


class FinanceSummaryDto(Object):
    revenue_minor: int = 0
    payments_by_status: Dict[str, int] = {}
    commissions_by_status: Dict[str, int] = {}
    payouts_by_status: Dict[str, int] = {}
    pending_payouts: int = 0
