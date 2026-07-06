"""Earnings DTOs (PRD §15.1). No entity — the earnings surface is derived from the
commission ledger + payouts (D31)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from main.app.core.state.status import AgentRole, VerificationTier
from main.appodus_utils import Object
from main.appodus_utils.db.types.money import TransactionCurrency


class EarningsSummaryDto(Object):
    """The agent earnings dashboard figures (§15.1) — all in integer minor units.

    ``available`` is the single hero figure the agent anchors on; the rest are the
    explained secondary line items."""

    available_minor: int
    clearing_minor: int
    in_reserve_minor: int
    on_hold_minor: int
    lifetime_earned_minor: int
    total_paid_minor: int
    pending_payout_minor: int
    currency: TransactionCurrency = TransactionCurrency.NGN


class EarningJobDto(Object):
    """One commission line in the per-job breakdown (§15.1)."""

    id: str
    verification_id: str
    role: AgentRole
    tier: VerificationTier
    amount_minor: int
    reserve_amount_minor: int
    status: str          # CLEARING / AVAILABLE / FROZEN / REVERSED
    cleared: bool        # bulk clearance date passed
    reserve_released: bool
    clearing_until: Optional[datetime] = None
    reserve_until: Optional[datetime] = None
    date_created: datetime
