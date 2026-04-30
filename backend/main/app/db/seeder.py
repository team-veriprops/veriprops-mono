from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

from kink import di, inject

from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.transactional import transactional, TransactionSessionPolicy

logger: Logger = di['logger']


@inject
@decorate_all_methods(transactional(session_policy=TransactionSessionPolicy.ALWAYS_NEW), exclude=['__init__'])
class DataSeeder:
    """Reference data (consent documents, super admin, …) is seeded at the
    Alembic migration layer. This runtime seeder is intentionally a no-op —
    keep it here as the lifespan hook so future *runtime-only* seeds (cache
    warm-up, denormalised views) have a home.
    """

    def __init__(self):
        self.seeded = False

    async def run_data_seed(self):
        if self.seeded:
            return
        self.seeded = True
