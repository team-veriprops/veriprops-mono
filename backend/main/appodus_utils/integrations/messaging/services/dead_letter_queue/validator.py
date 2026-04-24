from kink import inject

from main.appodus_utils.exception.exceptions import ResourceNotFoundException
from main.appodus_utils.integrations.messaging.services.dead_letter_queue.repo import DLQRepo


@inject
class DLQValidator:
    def __init__(self, dLq_repo: DLQRepo):
        self._dLq_repo = dLq_repo

    async def should_exist_by_id(self, _id: str):
        if not (await self._dLq_repo.exists_by_id(_id)):
            raise ResourceNotFoundException("DLQs", _id)
