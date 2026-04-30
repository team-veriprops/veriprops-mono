from kink import inject

from main.app.domain.message.models import SearchMessageDto
from main.app.domain.message.repo import MessageRepo
from main.appodus_utils.exception.exceptions import ResourceNotFoundException


@inject
class MessageValidator:
    def __init__(self, message_repo: MessageRepo):
        self._message_repo = message_repo

    async def should_exist_by_id(self, _id: str):
        if not (await self._message_repo.exists_by_id(_id)):
            raise ResourceNotFoundException("Messages", _id)

    async def should_exist_by_user_id(self, user_id: str):
        search_dto = SearchMessageDto(user_id=user_id, size=1)
        response = await self._message_repo.exists_by_criterion(search_dto)

        if not response:
            raise ResourceNotFoundException("Messages", user_id, "User ID")

    async def should_exist_by_seller_id(self, seller_id: str):
        search_dto = SearchMessageDto(seller_id=seller_id, size=1)
        response = await self._message_repo.exists_by_criterion(search_dto)

        if not response:
            raise ResourceNotFoundException("Messages", seller_id, "SELLER ID")

    async def should_exist_by_agent_id(self, agent_id: str):
        search_dto = SearchMessageDto(agent_id=agent_id, size=1)
        response = await self._message_repo.exists_by_criterion(search_dto)

        if not response:
            raise ResourceNotFoundException("Messages", agent_id, "AGENT ID")

