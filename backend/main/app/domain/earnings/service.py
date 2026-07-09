"""Earnings service (PRD §15.1/§15.2, D31).

Derives the agent earnings dashboard (available / clearing / reserve / on-hold / lifetime /
paid) from the commission ledger + payouts, and runs the clearance sweep that moves cleared
money to available and fires the positive-movement notification (§15.1). Nothing is stored —
the balance is recomputed on read so it always reconciles to the kobo.
"""
from __future__ import annotations

from typing import Set

from kink import inject

from main.app.core.events import DomainEvent, EventType, publish_domain_event
from main.app.core.state.status import AgentRole, VerificationTier
from main.app.domain.commission.models import Commission, CommissionStatus, UpdateCommissionDto
from main.app.domain.commission.repo import CommissionRepo
from main.app.domain.earnings.calc import derive_balance
from main.app.domain.earnings.models import EarningJobDto, EarningsSummaryDto
from main.app.domain.payout.models import LOCKING_STATUSES, Payout, PayoutStatus
from main.app.domain.payout.repo import PayoutRepo
from main.appodus_utils import Utils
from main.appodus_utils.db.models import Page
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class EarningsService:
    def __init__(self, commission_repo: CommissionRepo, payout_repo: PayoutRepo):
        self._commissions = commission_repo
        self._payouts = payout_repo

    async def summary(self, agent_id: str) -> EarningsSummaryDto:
        commissions = await self._commissions.list_for_agent(agent_id)
        payouts = await self._payouts.list_for_agent(agent_id)
        total_paid = self._total_paid(payouts)
        pending_locked = self._pending_locked(payouts)
        balance = derive_balance(commissions, Utils.datetime_now(), total_paid, pending_locked)
        return EarningsSummaryDto(
            available_minor=balance.available_minor,
            clearing_minor=balance.clearing_minor,
            in_reserve_minor=balance.in_reserve_minor,
            on_hold_minor=balance.on_hold_minor,
            lifetime_earned_minor=balance.lifetime_earned_minor,
            total_paid_minor=balance.total_paid_minor,
            pending_payout_minor=pending_locked,
        )

    async def available_minor(self, agent_id: str) -> int:
        """Withdrawable balance (already nets out in-flight payouts) — used by PayoutService."""
        return (await self.summary(agent_id)).available_minor

    async def jobs_page(self, agent_id: str, page: int, page_size: int) -> Page[EarningJobDto]:
        rows, total = await self._commissions.page_for_agent(agent_id, page, page_size)
        now = Utils.datetime_now()
        dtos = [self._job_dto(c, now) for c in rows]
        return self._commissions._db_utils.build_page(dtos, total, page, page_size)

    async def sweep_cleared(self) -> int:
        """Move newly-cleared money to available (§15.2) and notify the agent once per pass.

        Pass 1 flips CLEARING→AVAILABLE when the bulk clearance date passes; pass 2 releases
        the reserve when its chargeback window passes. Idempotent: each pass only touches rows
        that have not yet transitioned. Returns the number of commissions advanced."""
        now = Utils.datetime_now()
        advanced = 0
        notify: Set[str] = set()

        for c in await self._commissions.list_clearing_due(now):
            await self._commissions.update(c.id, UpdateCommissionDto(status=CommissionStatus.AVAILABLE.value))
            notify.add(c.agent_id)
            advanced += 1

        for c in await self._commissions.list_reserve_due(now):
            row = await self._commissions.get_model(c.id)
            if row is not None and row.reserve_released_at is None:
                row.reserve_released_at = now
                notify.add(c.agent_id)
                advanced += 1

        for agent_id in notify:
            await publish_domain_event(DomainEvent(
                type=EventType.COMMISSION_CLEARED, recipient_user_ids=(agent_id,),
            ))
        return advanced

    # ── helpers ───────────────────────────────────────────────────

    @staticmethod
    def _total_paid(payouts: list[Payout]) -> int:
        return sum(
            (p.amount_minor + (p.adjustment_minor or 0))
            for p in payouts if p.status == PayoutStatus.PAID.value
        )

    @staticmethod
    def _pending_locked(payouts: list[Payout]) -> int:
        return sum(p.amount_minor for p in payouts if p.status in LOCKING_STATUSES)

    def _job_dto(self, c: Commission, now) -> EarningJobDto:
        cleared = c.clearing_until is not None and now >= c.clearing_until
        return EarningJobDto(
            id=c.id, verification_id=c.verification_id, role=AgentRole(c.role),
            tier=VerificationTier(c.tier), amount_minor=c.amount_minor,
            reserve_amount_minor=c.reserve_amount_minor or 0, status=c.status,
            cleared=cleared, reserve_released=c.reserve_released_at is not None,
            clearing_until=c.clearing_until, reserve_until=c.reserve_until,
            date_created=c.date_created,
        )
