from typing import List, Type
from sqlalchemy import select
from kink import inject
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.payout.models import (
    BankAccount, Payout, PayoutAdjustment,
    CreateBankAccountDto, UpdateBankAccountDto, QueryBankAccountDto, SearchBankAccountDto,
    CreatePayoutDto, UpdatePayoutDto, QueryPayoutDto, SearchPayoutDto,
    CreatePayoutAdjustmentDto,
)
from main.appodus_utils.db.repo import GenericRepo
from main.appodus_utils.db.session import get_db_session_from_context


@inject
class BankAccountRepo(GenericRepo[
    BankAccount, CreateBankAccountDto, UpdateBankAccountDto,
    QueryBankAccountDto, SearchBankAccountDto,
]):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[BankAccount] = BankAccount,
        query_dto: Type[QueryBankAccountDto] = QueryBankAccountDto,
    ):
        super().__init__(db, model, query_dto)


    async def list_for_agent(self, agent_id: str) -> List[BankAccount]:
        result = await self._session.execute(
            select(BankAccount).where(
                BankAccount.agent_id == agent_id, BankAccount.deleted == False
            )
        )
        return list(result.scalars().all())


@inject
class PayoutRepo(GenericRepo[
    Payout, CreatePayoutDto, UpdatePayoutDto, QueryPayoutDto, SearchPayoutDto,
]):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[Payout] = Payout,
        query_dto: Type[QueryPayoutDto] = QueryPayoutDto,
    ):
        super().__init__(db, model, query_dto)

    async def list_for_agent(self, agent_id: str) -> List[Payout]:
        result = await self._session.execute(
            select(Payout).where(
                Payout.agent_id == agent_id, Payout.deleted == False
            ).order_by(Payout.date_created.desc())
        )
        return list(result.scalars().all())


@inject
class PayoutAdjustmentRepo(GenericRepo[
    PayoutAdjustment, CreatePayoutAdjustmentDto, CreatePayoutAdjustmentDto,
    QueryPayoutDto, SearchPayoutDto,
]):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[PayoutAdjustment] = PayoutAdjustment,
        query_dto: Type[QueryPayoutDto] = QueryPayoutDto,
    ):
        super().__init__(db, model, query_dto)
