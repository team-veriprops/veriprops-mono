from kink import inject

from main.app.domain.bank.models import SearchBankDto
from main.app.domain.bank.repo import BankRepo
from main.appodus_utils.exception.exceptions import ResourceConflictException


@inject
class BankValidator:
    def __init__(self, bank_repo: BankRepo):
        self._bank_repo = bank_repo

    async def should_exist_by_id(self, _id: str):
        if not (await self._bank_repo.exists_by_id(_id)):
            raise ResourceConflictException("Banks", "No bank found")

    async def should_exist_by_code(self, bank_code: str):
        search_dto: SearchBankDto = SearchBankDto(code=bank_code)
        if not (await self._bank_repo.exists_by_criterion(search_dto)):
            raise ResourceConflictException("Banks", f"No bank found with code '{bank_code}'")
