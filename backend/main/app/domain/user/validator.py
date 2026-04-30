from kink import inject

from main.app.domain.user.repo import UserRepo
from main.appodus_utils.exception.exceptions import (
    ResourceNotFoundException,
    UserAlreadyExistsException,
    UserNotFoundException,
)


@inject
class UserValidator:
    def __init__(self, user_repo: UserRepo):
        self._user_repo = user_repo

    async def should_exist_by_id(self, user_id: str):
        if not (await self._user_repo.exists_by_id(user_id)):
            raise UserNotFoundException(user_id=user_id)

    async def should_not_exist_by_email(self, email: str):
        if await self._user_repo.get_by_email(email):
            raise UserAlreadyExistsException(email=email)

    async def get_by_email_or_raise(self, email: str):
        user = await self._user_repo.get_by_email(email)
        if not user:
            raise ResourceNotFoundException("User", f"No user with email {email}")
        return user
