"""Agent bank account service (PRD §15.1)."""
from __future__ import annotations

from typing import List

from kink import inject

from main.app.domain.payout.bank_account.models import (
    AddBankAccountDto,
    AgentBankAccount,
    CreateBankAccountDto,
    UpdateBankAccountDto,
)
from main.app.domain.payout.bank_account.repo import BankAccountRepo
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import ResourceNotFoundException


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class BankAccountService:
    def __init__(self, bank_account_repo: BankAccountRepo):
        self._repo = bank_account_repo

    async def list_for_agent(self, agent_id: str) -> List[AgentBankAccount]:
        return await self._repo.list_for_agent(agent_id)

    async def add(self, agent_id: str, dto: AddBankAccountDto) -> AgentBankAccount:
        """Store a beneficiary. When marked default, demote any existing default first."""
        make_default = dto.is_default or not await self._repo.list_for_agent(agent_id)
        if make_default:
            await self._clear_default(agent_id)
        return await self._repo.create_return_model(CreateBankAccountDto(
            agent_id=agent_id, bank_name=dto.bank_name, account_number=dto.account_number,
            account_name=dto.account_name, is_default=make_default,
        ))

    async def remove(self, agent_id: str, account_id: str) -> None:
        account = await self._get_owned(account_id, agent_id)
        await self._repo.soft_delete(account.id)

    async def make_default(self, agent_id: str, account_id: str) -> AgentBankAccount:
        account = await self._get_owned(account_id, agent_id)
        await self._clear_default(agent_id)
        await self._repo.update(account.id, UpdateBankAccountDto(is_default=True))
        return await self._repo.get_model(account.id)

    # ── helpers ───────────────────────────────────────────────────

    async def _get_owned(self, account_id: str, agent_id: str) -> AgentBankAccount:
        account = await self._repo.get_model(account_id)
        if account is None or account.deleted or account.agent_id != agent_id:
            raise ResourceNotFoundException(resource="bank_account")
        return account

    async def _clear_default(self, agent_id: str) -> None:
        for existing in await self._repo.list_for_agent(agent_id):
            if existing.is_default:
                await self._repo.update(existing.id, UpdateBankAccountDto(is_default=False))
