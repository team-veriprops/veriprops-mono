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
    def __init__(
            self,
    ):
        self.seeded = False

    async def run_data_seed(self):
        if self.seeded:
            return

        # await self._create_super_admin()

        self.seeded = True
