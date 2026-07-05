from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

from kink import di, inject

from main.app.domain.system_config.service import ConfigService
from main.app.domain.user.auth.consent.service import ConsentService
from main.app.domain.verification.scoring.service import TrustScoreWeightService
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.transactional import transactional, TransactionSessionPolicy

logger: Logger = di['logger']


@inject
@decorate_all_methods(transactional(session_policy=TransactionSessionPolicy.ALWAYS_NEW), exclude=['__init__'])
class DataSeeder:
    """Startup seeder. Schema rows are created by the migration; legal-document
    bodies and sign-off status are refreshed here from the content registry, and the
    default Trust Score Weights are seeded idempotently (§8.3 / D14)."""

    def __init__(
        self,
        consent_service: ConsentService,
        trust_weight_service: TrustScoreWeightService,
        config_service: ConfigService,
    ):
        self.seeded = False
        self._consent_service = consent_service
        self._trust_weight_service = trust_weight_service
        self._config_service = config_service

    async def run_data_seed(self):
        if self.seeded:
            return
        await self._consent_service.seed_documents()
        await self._trust_weight_service.seed_defaults()
        await self._config_service.seed_defaults()
        self.seeded = True
