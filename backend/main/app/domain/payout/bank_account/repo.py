"""Agent bank account data access."""
from __future__ import annotations

from typing import List, Type

from kink import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.payout.bank_account.models import (
    AgentBankAccount,
    CreateBankAccountDto,
    QueryBankAccountDto,
    SearchBankAccountDto,
    UpdateBankAccountDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class BankAccountRepo(
    GenericRepo[
        AgentBankAccount,
        CreateBankAccountDto,
        UpdateBankAccountDto,
        QueryBankAccountDto,
        SearchBankAccountDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[AgentBankAccount] = AgentBankAccount,
        query_dto: Type[QueryBankAccountDto] = QueryBankAccountDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def list_for_agent(self, agent_id: str) -> List[AgentBankAccount]:
        stmt = select(AgentBankAccount).where(
            AgentBankAccount.deleted.is_(False), AgentBankAccount.agent_id == agent_id
        ).order_by(AgentBankAccount.is_default.desc(), AgentBankAccount.date_created.desc())
        return list((await self._session.execute(stmt)).scalars().all())
