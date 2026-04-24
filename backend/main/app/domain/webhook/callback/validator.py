from kink import inject

from main.app.domain.webhook.callback.repo import CallbackRepo
from main.appodus_utils.exception.exceptions import ResourceNotFoundException


@inject
class CallbackValidator:
    def __init__(self, callback_repo: CallbackRepo):
        self._callback_repo = callback_repo

    async def should_exist_by_id(self, _id: str):
        if not (await self._callback_repo.exists_by_id(_id)):
            raise ResourceNotFoundException("Callbacks", _id)
