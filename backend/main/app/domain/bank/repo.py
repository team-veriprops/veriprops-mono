from typing import Type

from kink import inject
from main.app.domain.bank.models import Bank, CreateBankDto, UpdateBankDto, SearchBankDto, QueryBankDto
from sqlalchemy.ext.asyncio import AsyncSession

from main.appodus_utils.db.repo import GenericRepo


@inject
class BankRepo(GenericRepo[Bank, CreateBankDto, UpdateBankDto, QueryBankDto, SearchBankDto]):
    def __init__(self, db: AsyncSession, model: Type[Bank] = Bank, query_dto: Type[QueryBankDto] = QueryBankDto):
        super().__init__(db, model, query_dto)
        self.db = db
