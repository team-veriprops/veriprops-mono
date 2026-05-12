from kink import inject
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
    model = TierUpgrade
