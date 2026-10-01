from kink import inject

from main.app.domain.message.repo import MessageRepo
from main.appodus_utils.exception.exceptions import ResourceNotFoundException


@inject
class MessageValidator:
    def __init__(self, message_repo: MessageRepo):
        self._message_repo = message_repo

    async def should_exist_by_id(self, _id: str):
        if not (await self._message_repo.exists_by_id(_id)):
            raise ResourceNotFoundException("Message")
