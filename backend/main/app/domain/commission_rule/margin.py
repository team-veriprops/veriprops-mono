"""The commission margin guard (PRD §20.1 / D97).

Each role is paid a fixed commission and each tier carries its own price, set on two different
admin screens. Nothing ties them together, so a price cut or a commission raise could leave a
tier paying out more to its agents than the platform keeps. The guard is that tie: for every
tier, what the roles it needs can be paid must leave at least ``commission_min_margin_pct`` of the
tier's price. "What they can be paid" is the worst case: each role's fixed commission plus the
remote bonus (``remote_job_bonus_ngn_kobo``), since any of the tier's tasks may age out of the pool.

It runs before each of the four writes that can break the rule — a role's commission, a tier's
price, the minimum margin, the remote bonus — with the proposed value merged over what is stored.
It reads repositories rather than services so all three writing services can depend on it without
a cycle. `test_margin_guard_coverage.py` fails on any writer that skips it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Optional

from kink import inject

from main.app.core.money_text import naira
from main.app.core.state.dependencies import roles_for_tier
from main.app.core.state.status import AgentRole, VerificationTier
from main.app.domain.commission_rule.repo import CommissionRuleRepo
from main.app.domain.system_config.models import ConfigKey, effective_config_value
from main.app.domain.system_config.repo import SystemConfigRepo
from main.app.domain.verification.pricing import effective_tier_price
from main.app.domain.verification.pricing_config.repo import PricingTierConfigRepo
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import ValidationException


@dataclass(frozen=True)
class MarginBreach:
    """The first tier whose commissions would leave less than the minimum margin."""

    tier: VerificationTier
    price_minor: int
    commissions_minor: int     # the tier's worst-case agent pay: commissions plus remote bonuses
    min_margin_pct: int
    remote_bonus_minor: int = 0

    @property
    def margin_pct(self) -> float:
        kept = self.price_minor - self.commissions_minor
        return 100 * kept / self.price_minor if self.price_minor else 0.0

    def message(self) -> str:
        kept = self.price_minor - self.commissions_minor
        paid_as = "agent commissions and remote bonuses" if self.remote_bonus_minor else "agent commissions"
        return (
            f"{self.tier.value.capitalize()} would keep {naira(kept)} of its "
            f"{naira(self.price_minor)} price after paying {naira(self.commissions_minor)} in "
            f"{paid_as} ({self.margin_pct:.0f}%), below the {self.min_margin_pct}% minimum margin."
        )


def find_margin_breach(
    prices: Mapping[VerificationTier, int],
    commissions: Mapping[AgentRole, int],
    min_margin_pct: int,
    remote_bonus_minor: int = 0,
) -> Optional[MarginBreach]:
    """The first tier (in ``VerificationTier`` order) that breaks the margin rule, or None.

    A tier breaks it when ``price − Σ (commission(role) + bonus) < min_margin_pct % × price`` over
    the roles the tier requires. Integer arithmetic, so a margin exactly at the minimum passes."""
    for tier in VerificationTier:
        if tier not in prices:
            continue
        price = prices[tier]
        paid = sum(commissions.get(role, 0) + remote_bonus_minor for role in roles_for_tier(tier))
        if (price - paid) * 100 < min_margin_pct * price:
            return MarginBreach(tier=tier, price_minor=price, commissions_minor=paid,
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
    ) -> None:
        """Refuse (``ValidationException``) when the stored configuration, with the proposed
        values merged over it, leaves any tier below the minimum margin."""
        commissions = {**await self._stored_commissions(), **(commission_overrides or {})}
        prices = {**await self._stored_prices(), **(price_overrides or {})}
        margin = min_margin_pct if min_margin_pct is not None else await self._stored_int(
            ConfigKey.COMMISSION_MIN_MARGIN_PCT)
        bonus = remote_bonus_minor if remote_bonus_minor is not None else await self._stored_int(
            ConfigKey.REMOTE_JOB_BONUS_NGN_KOBO)
        breach = find_margin_breach(prices, commissions, margin, bonus)
        if breach is not None:
            raise ValidationException(message=breach.message())

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
