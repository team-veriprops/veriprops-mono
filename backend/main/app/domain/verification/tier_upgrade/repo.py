from typing import Type

from kink import inject
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.verification.tier_upgrade.models import (
    TierUpgrade, CreateTierUpgradeDto, UpdateTierUpgradeDto,
    QueryTierUpgradeDto, SearchTierUpgradeDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class TierUpgradeRepo(GenericRepo[
    TierUpgrade, CreateTierUpgradeDto, UpdateTierUpgradeDto,
    QueryTierUpgradeDto, SearchTierUpgradeDto,
]):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[TierUpgrade] = TierUpgrade,
        query_dto: Type[QueryTierUpgradeDto] = QueryTierUpgradeDto,
    ):
        super().__init__(db, model, query_dto)
