"""The commission margin guard (PRD §20.1 / D97).

Each role is paid a fixed commission and each tier carries its own price, set on two different
admin screens. Nothing ties them together, so a price cut or a commission raise could leave a
tier paying out more to its agents than the platform keeps. The guard is that tie: for every
tier, what the roles it needs can be paid must leave at least ``commission_min_margin_pct`` of
what the tier collects. Both sides are the worst case:

- *Collected* is the price after the largest discount a customer can get (§17.1): the first-time
  discount, topped up by referral credit to the combined cap. Agents are paid in full on a
  discounted case, so the discount comes out of the platform's share alone.
- *Paid* is each role's fixed commission plus the remote bonus (``remote_job_bonus_ngn_kobo``),
  since any of the tier's tasks may age out of the pool.

It runs before each of the six writes that can break the rule — a role's commission, a tier's
price, the minimum margin, the remote bonus and the two discount percentages — with the proposed
value merged over what is stored, under one global lock so two saves cannot each pass against
the other's stale value. It reads repositories rather than services so all three writing services
can depend on it without a cycle. `test_margin_guard_coverage.py` fails on any writer that skips it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Mapping, Optional

from kink import inject

from main.app.core.money_text import naira
from main.app.core.state.dependencies import roles_for_tier
from main.app.core.state.status import AgentRole, VerificationTier
from main.app.domain.commission_rule.repo import CommissionRuleRepo
from main.app.domain.system_config.models import ConfigKey, effective_config_value
from main.app.domain.system_config.repo import SystemConfigRepo
from main.app.domain.verification.pricing import apply_discounts, effective_tier_price
from main.app.domain.verification.pricing_config.repo import PricingTierConfigRepo
from main.appodus_utils.db.locks import advisory_xact_lock
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import ValidationException

# Advisory-lock name: every margin-affecting save checks and writes in turn.
_MARGIN_LOCK = "commission_margin"


@dataclass(frozen=True)
class MarginBreach:
    """The first tier whose commissions would leave less than the minimum margin."""

    tier: VerificationTier
    price_minor: int
    net_minor: int             # what the tier collects after the largest discount
    commissions_minor: int     # the tier's worst-case agent pay: commissions plus remote bonuses
    min_margin_pct: int
    remote_bonus_minor: int = 0

    @property
    def margin_pct(self) -> float:
        kept = self.net_minor - self.commissions_minor
        return 100 * kept / self.net_minor if self.net_minor else 0.0

    @property
    def margin_pct_text(self) -> str:
        """The margin cut (never rounded) to one decimal, so a figure just under the minimum
        never reads as the minimum itself: 29.96% shows as 29.9%, not 30%."""
        tenths = math.floor(self.margin_pct * 10) / 10
        return f"{tenths:g}%"

    def message(self) -> str:
        kept = self.net_minor - self.commissions_minor
        paid_as = "agent commissions and remote bonuses" if self.remote_bonus_minor else "agent commissions"
        collected = (
            f"{naira(self.net_minor)} it collects after the largest discount on its "
            f"{naira(self.price_minor)} price"
            if self.net_minor != self.price_minor else f"{naira(self.price_minor)} price"
        )
        return (
            f"{self.tier.value.capitalize()} would keep {naira(kept)} of the {collected} after "
            f"paying {naira(self.commissions_minor)} in {paid_as} ({self.margin_pct_text}), below "
            f"the {self.min_margin_pct}% minimum margin."
        )


def worst_case_net_minor(price_minor: int, first_time_pct: int, max_discount_pct: int) -> int:
    """The least a case at *price_minor* can collect: a first-time customer whose referral credit
    fills the rest of the combined cap — the same arithmetic the quote applies (§17.1)."""
    return apply_discounts(
        price_minor, first_time=True, first_time_pct=first_time_pct,
        referral_credit_kobo=price_minor, max_discount_pct=max_discount_pct,
    ).net_minor


def find_margin_breach(
    prices: Mapping[VerificationTier, int],
    commissions: Mapping[AgentRole, int],
    min_margin_pct: int,
    remote_bonus_minor: int = 0,
    *,
    first_time_pct: int = 0,
    max_discount_pct: int = 0,
) -> Optional[MarginBreach]:
    """The first tier (in ``VerificationTier`` order) that breaks the margin rule, or None.

    A tier breaks it when ``net − Σ (commission(role) + bonus) < min_margin_pct % × net``, over the
    roles the tier requires, where *net* is the price after the largest discount. Integer
    arithmetic, so a margin exactly at the minimum passes."""
    for tier in VerificationTier:
        if tier not in prices:
            continue
        price = prices[tier]
        net = worst_case_net_minor(price, first_time_pct, max_discount_pct)
        paid = sum(commissions.get(role, 0) + remote_bonus_minor for role in roles_for_tier(tier))
        if (net - paid) * 100 < min_margin_pct * net:
            return MarginBreach(tier=tier, price_minor=price, net_minor=net, commissions_minor=paid,
                                min_margin_pct=min_margin_pct, remote_bonus_minor=remote_bonus_minor)
    return None


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class CommissionMarginGuard:
    def __init__(
        self,
        commission_rule_repo: CommissionRuleRepo,
        pricing_tier_config_repo: PricingTierConfigRepo,
        system_config_repo: SystemConfigRepo,
    ):
        self._commission_rule_repo = commission_rule_repo
        self._pricing_tier_config_repo = pricing_tier_config_repo
        self._system_config_repo = system_config_repo

    async def check(
        self,
        *,
        commission_overrides: Optional[Mapping[AgentRole, int]] = None,
        price_overrides: Optional[Mapping[VerificationTier, int]] = None,
        min_margin_pct: Optional[int] = None,
        remote_bonus_minor: Optional[int] = None,
        first_time_pct: Optional[int] = None,
        max_discount_pct: Optional[int] = None,
    ) -> None:
        """Refuse (``ValidationException``) when the stored configuration, with the proposed
        values merged over it, leaves any tier below the minimum margin.

        Takes the global margin lock before reading anything, held until the caller's
        transaction ends: the caller writes its value in that same transaction, so the next
        save's check reads it rather than the value this one replaced."""
        await advisory_xact_lock(_MARGIN_LOCK)
        commissions = {**await self._stored_commissions(), **(commission_overrides or {})}
        prices = {**await self._stored_prices(), **(price_overrides or {})}
        breach = find_margin_breach(
            prices, commissions,
            await self._proposed_or_stored(min_margin_pct, ConfigKey.COMMISSION_MIN_MARGIN_PCT),
            await self._proposed_or_stored(remote_bonus_minor, ConfigKey.REMOTE_JOB_BONUS_NGN_KOBO),
            first_time_pct=await self._proposed_or_stored(first_time_pct, ConfigKey.FIRST_TIME_DISCOUNT_PERCENT),
            max_discount_pct=await self._proposed_or_stored(max_discount_pct, ConfigKey.MAX_DISCOUNT_PERCENT),
        )
        if breach is not None:
            raise ValidationException(message=breach.message())

    async def _proposed_or_stored(self, proposed: Optional[int], key: ConfigKey) -> int:
        return proposed if proposed is not None else await self._stored_int(key)

    async def _stored_commissions(self) -> Dict[AgentRole, int]:
        # An unconfigured role pays nothing, the same rule CommissionRuleService applies.
        rows = {r.role: int(r.amount_ngn_kobo) for r in await self._commission_rule_repo.list_all()}
        return {role: rows.get(role.value, 0) for role in AgentRole}

    async def _stored_prices(self) -> Dict[VerificationTier, int]:
        rows = {r.tier: r.price_ngn_kobo for r in await self._pricing_tier_config_repo.list_all()}
        return {tier: effective_tier_price(rows.get(tier.value), tier) for tier in VerificationTier}

    async def _stored_int(self, key: ConfigKey) -> int:
        row = await self._system_config_repo.get_by_key(key.value)
        stored = row.value_json if row is not None else None
        return int(effective_config_value(stored, key))
