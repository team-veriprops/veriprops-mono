"""Agent bank account service (PRD §15.1).

An account is saved only as the bank holds it: the bank comes from the gateway's own list,
and the name from the gateway's account lookup, asked again here even when the screen
already showed it.
"""
from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple

from kink import inject

from main.app.config.settings import IntegratedPlatform
from main.app.domain.payout.bank_account.models import (
    AddBankAccountDto,
    AgentBankAccount,
    BankDto,
    CreateBankAccountDto,
    ResolveBankAccountDto,
    ResolvedBankAccountDto,
    UpdateBankAccountDto,
)
from main.app.domain.payout.bank_account.repo import BankAccountRepo
from main.appodus_utils.db.types.money import TransactionCurrency
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import ResourceNotFoundException, ValidationException
from main.appodus_utils.integrations.factory import PaymentGatewayFactory

# Banks change rarely and the list is a few hundred rows: fetched per gateway, kept a while.
_BANK_CACHE_SECONDS = 12 * 60 * 60
_BANK_CACHE: Dict[Optional[IntegratedPlatform], Tuple[float, List[BankDto]]] = {}


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class BankAccountService:
    def __init__(self, bank_account_repo: BankAccountRepo, gateway_factory: PaymentGatewayFactory):
        self._bank_account_repo = bank_account_repo
        self._gateways = gateway_factory

    async def list_for_agent(self, agent_id: str) -> List[AgentBankAccount]:
        return await self._bank_account_repo.list_for_agent(agent_id)

    async def list_banks(self) -> List[BankDto]:
        """The banks a new account can be saved with: the list of the gateway that resolves it."""
        platform = self._gateways.transfer_platform()
        cached = _BANK_CACHE.get(platform)
        if cached and time.monotonic() - cached[0] < _BANK_CACHE_SECONDS:
            return cached[1]
        banks = [
            BankDto(code=b.code, name=b.name)
            for b in await self._gateways.transfers(platform).list_banks(TransactionCurrency.NGN)
        ]
        banks.sort(key=lambda b: b.name.lower())
        _BANK_CACHE[platform] = (time.monotonic(), banks)
        return banks

    async def resolve(self, dto: ResolveBankAccountDto) -> ResolvedBankAccountDto:
        """The account as the bank holds it; refused when the bank knows no such account."""
        bank = next((b for b in await self.list_banks() if b.code == dto.bank_code), None)
        if bank is None:
            raise ValidationException(message="Choose your bank from the list.")
        platform = self._gateways.transfer_platform()
        account = await self._gateways.transfers(platform).resolve_account(dto.bank_code, dto.account_number)
        if account is None:
            raise ValidationException(
                message="The bank has no account with that number. Check the number and the bank."
            )
        return ResolvedBankAccountDto(
            bank_code=dto.bank_code, bank_name=bank.name,
            account_number=dto.account_number, account_name=account.account_name,
        )

    async def add(self, agent_id: str, dto: AddBankAccountDto) -> AgentBankAccount:
        """Store a beneficiary as the bank holds it. When marked default, demote any existing
        default first; the first account is the default."""
        existing = await self._bank_account_repo.list_for_agent(agent_id)
        if any(a.bank_code == dto.bank_code and a.account_number == dto.account_number for a in existing):
            raise ValidationException(message="This account is already saved.")
        resolved = await self.resolve(dto)
        platform = self._gateways.transfer_platform()
        make_default = dto.is_default or not existing
        if make_default:
            await self._clear_default(agent_id)
        return await self._bank_account_repo.create_return_model(CreateBankAccountDto(
            agent_id=agent_id, bank_name=resolved.bank_name, bank_code=resolved.bank_code,
            provider=platform.value if platform else None,
            account_number=resolved.account_number, account_name=resolved.account_name,
            is_default=make_default,
        ))

    async def get_owned(self, agent_id: str, account_id: str) -> AgentBankAccount:
        """The agent's own live account; anyone else's is simply not found."""
        return await self._get_owned(account_id, agent_id)

    async def remove(self, agent_id: str, account_id: str) -> None:
        account = await self._get_owned(account_id, agent_id)
        await self._bank_account_repo.soft_delete(account.id)

    async def make_default(self, agent_id: str, account_id: str) -> AgentBankAccount:
        account = await self._get_owned(account_id, agent_id)
        await self._clear_default(agent_id)
        await self._bank_account_repo.update(account.id, UpdateBankAccountDto(is_default=True))
        return await self._bank_account_repo.get_model(account.id)

    # ── helpers ───────────────────────────────────────────────────

    async def _get_owned(self, account_id: str, agent_id: str) -> AgentBankAccount:
        account = await self._bank_account_repo.get_model(account_id)
        if account is None or account.deleted or account.agent_id != agent_id:
            raise ResourceNotFoundException(resource="bank_account")
        return account

    async def _clear_default(self, agent_id: str) -> None:
        for existing in await self._bank_account_repo.list_for_agent(agent_id):
            if existing.is_default:
                await self._bank_account_repo.update(existing.id, UpdateBankAccountDto(is_default=False))
