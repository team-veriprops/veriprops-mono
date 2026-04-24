from http import HTTPStatus

from fastapi import APIRouter, Depends
from kink import di

from main.appodus_utils import Page
from main.app.domain.bank.models import QueryBankDto, CreateBankDto, SearchBankDto, UpdateBankDto
from main.app.domain.bank.service import BankService
from main.appodus_utils.db.models import SuccessResponse

bank_service: BankService = di[BankService]
bank_router = APIRouter(prefix="/banks", tags=["Banks"])


@bank_router.post('/', response_model=SuccessResponse[QueryBankDto], status_code=HTTPStatus.CREATED)
async def create_bank(create_dto: CreateBankDto) -> SuccessResponse[QueryBankDto]:
    return await bank_service.create_bank(create_dto)


@bank_router.get('/{bank_id}', response_model=SuccessResponse[QueryBankDto], status_code=HTTPStatus.OK)
async def get_bank(bank_id: str) -> SuccessResponse[QueryBankDto]:
    return await bank_service.get_bank(bank_id)


@bank_router.get('/', response_model=Page[QueryBankDto], status_code=HTTPStatus.OK)
async def get_bank_page(search_dto: SearchBankDto = Depends()) -> Page[QueryBankDto]:
    return await bank_service.get_bank_page(search_dto)


@bank_router.put('/{bank_id}', response_model=SuccessResponse[QueryBankDto], status_code=HTTPStatus.OK)
async def update_bank(bank_id: str, obj_in: UpdateBankDto) -> SuccessResponse[QueryBankDto]:
    return await bank_service.update_bank(bank_id, obj_in)


@bank_router.patch('/{bank_id}/name', response_model=SuccessResponse[bool], status_code=HTTPStatus.OK)
async def update_bank_name(bank_id: str, bank_name: str) -> SuccessResponse[bool]:
    return await bank_service.update_bank_name(bank_id, bank_name)


@bank_router.patch('/{bank_id}/deactivate', response_model=SuccessResponse[bool], status_code=HTTPStatus.OK)
async def deactivate_bank(bank_id: str) -> SuccessResponse[bool]:
    return await bank_service.deactivate_bank(bank_id)


@bank_router.patch('/{bank_id}/activate', response_model=SuccessResponse[bool], status_code=HTTPStatus.OK)
async def activate_bank(bank_id: str) -> SuccessResponse[bool]:
    return await bank_service.activate_bank(bank_id)


@bank_router.delete('/{bank_id}', response_model=SuccessResponse[bool], status_code=HTTPStatus.OK)
async def soft_delete_bank(bank_id: str) -> SuccessResponse[bool]:
    return await bank_service.soft_delete_bank(bank_id)
