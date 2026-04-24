from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

from kink import inject, di

from main.appodus_utils import Page
from main.app.domain.bank.models import (
    CreateBankDto,
    QueryBankDto,
    UpdateBankDto,
    SearchBankDto,
    _UpdateBankDto)
from main.app.domain.bank.repo import BankRepo
from main.app.domain.bank.validator import BankValidator
from main.appodus_utils.db.models import SuccessResponse
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional

logger: Logger = di['logger']


@inject
@decorate_all_methods(transactional(), exclude=['__init__'], exclude_startswith=['_'])
@decorate_all_methods(method_trace_logger, exclude=['__init__'], exclude_startswith=['_'])
class BankService:
    def __init__(self, bank_repo: BankRepo, bank_validator: BankValidator):
        self._bank_repo = bank_repo
        self._bank_validator = bank_validator

    async def create_bank(self, obj_in: CreateBankDto) -> SuccessResponse[QueryBankDto]:
        return await self._bank_repo.create(obj_in)

    async def get_bank(self, bank_id: str) -> SuccessResponse[QueryBankDto]:
        await self._bank_validator.should_exist_by_id(bank_id)
        return await self._bank_repo.get(bank_id)

    async def get_bank_by_code(self, bank_code: str) -> list[QueryBankDto]:
        await self._bank_validator.should_exist_by_code(bank_code)
        search_dto: SearchBankDto = SearchBankDto(code=bank_code)
        return await self._bank_repo.get_by_criterion(search_dto)

    async def get_bank_page(self, search_dto: SearchBankDto) -> Page[QueryBankDto]:
        return await self._bank_repo.get_page(search_dto=search_dto)

    async def update_bank(self, bank_id: str, obj_in: UpdateBankDto) -> SuccessResponse[QueryBankDto]:
        await self._bank_validator.should_exist_by_id(bank_id)
        return await self._bank_repo.update(bank_id, obj_in)

    async def update_bank_name(self, bank_id: str, bank_name: str) -> SuccessResponse[bool]:
        await self._bank_validator.should_exist_by_id(bank_id)
        obj_in = _UpdateBankDto(name=bank_name)
        await self._bank_repo.update(bank_id, obj_in.model_dump(exclude_none=True))

        return SuccessResponse(data=True)

    async def activate_bank(self, bank_id: str) -> SuccessResponse[bool]:
        await self._bank_validator.should_exist_by_id(bank_id)
        obj_in = _UpdateBankDto(status='ENABLED')
        await self._bank_repo.update(bank_id, obj_in.model_dump(exclude_none=True))

        return SuccessResponse(data=True)

    async def deactivate_bank(self, bank_id: str) -> SuccessResponse[bool]:
        await self._bank_validator.should_exist_by_id(bank_id)
        obj_in = _UpdateBankDto(status='DISABLED')
        await self._bank_repo.update(bank_id, obj_in.model_dump(exclude_none=True))

        return SuccessResponse(data=True)

    async def soft_delete_bank(self, bank_id: str) -> SuccessResponse[bool]:
        await self._bank_validator.should_exist_by_id(bank_id)
        await self._bank_repo.soft_delete(bank_id)

        return SuccessResponse(data=True)
