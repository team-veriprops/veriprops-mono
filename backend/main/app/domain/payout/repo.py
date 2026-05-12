from typing import List
from sqlalchemy import select
from kink import inject
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
    model = BankAccount

    async def list_for_agent(self, agent_id: str) -> List[BankAccount]:
        session = get_db_session_from_context()
        result = await session.execute(
            select(BankAccount).where(
                BankAccount.agent_id == agent_id, BankAccount.deleted == False
            )
        )
        return list(result.scalars().all())


@inject
class PayoutRepo(GenericRepo[
    Payout, CreatePayoutDto, UpdatePayoutDto, QueryPayoutDto, SearchPayoutDto,
]):
    model = Payout

    async def list_for_agent(self, agent_id: str) -> List[Payout]:
        session = get_db_session_from_context()
        result = await session.execute(
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
    model = PayoutAdjustment
