from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

from kink import di, inject

from main.app.domain.user.auth.consent.service import ConsentService
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.transactional import transactional, TransactionSessionPolicy

logger: Logger = di['logger']


@inject
@decorate_all_methods(transactional(session_policy=TransactionSessionPolicy.ALWAYS_NEW), exclude=['__init__'])
class DataSeeder:
    """Reference-data seeder run on startup.

    Document metadata (consent rows, super admin) is created at the Alembic
    migration layer; code-derived editorial content (legal-document Markdown
    bodies + sign-off status) is refreshed here from the content registry so the
    prose stays in maintainable Python modules rather than the migration.
    """

    def __init__(self, consent_service: ConsentService):
        self.seeded = False
        self._consent_service = consent_service

    async def run_data_seed(self):
        if self.seeded:
            return
        await self._consent_service.seed_documents()
        self.seeded = True
