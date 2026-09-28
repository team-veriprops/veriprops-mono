"""BankAccountService — a payout beneficiary is only ever what the bank says it is (§15.1).

The agent names a bank (from the gateway's own list) and an account number. The name
stored, and later paid, is the one the bank returns for that pair — never one the agent
typed — and the account remembers which gateway resolved it, because bank codes are only
meaningful to the gateway whose list they came from.
"""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.config.settings import IntegratedPlatform
from main.app.domain.payout.bank_account import service as bank_module
from main.app.domain.payout.bank_account.models import AddBankAccountDto, ResolveBankAccountDto
from main.app.domain.payout.bank_account.service import BankAccountService
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.db.types.money import TransactionCurrency
from main.appodus_utils.exception.exceptions import ResourceNotFoundException, ValidationException
from main.appodus_utils.integrations.payment.gateway.models import GatewayAccount, GatewayBank


@pytest.fixture(autouse=True)
def mock_db_session():
    session = MagicMock()
    session.in_transaction.return_value = False

    @asynccontextmanager
    async def _begin():
        yield

    session.begin = _begin
    session.flush = AsyncMock()
    token = db_session_ctx.set(session)
    yield session
    db_session_ctx.reset(token)


@pytest.fixture(autouse=True)
def fresh_bank_cache(monkeypatch):
    monkeypatch.setattr(bank_module, "_BANK_CACHE", {})


def _service(platform=IntegratedPlatform.PAYSTACK, resolved="ADA OBI", existing=()):
    svc = object.__new__(BankAccountService)
    svc._bank_account_repo = AsyncMock()
    svc._bank_account_repo.list_for_agent = AsyncMock(return_value=list(existing))
    svc._bank_account_repo.create_return_model = AsyncMock(side_effect=lambda dto: SimpleNamespace(
        id="ba-1", deleted=False, **dto.model_dump(),
    ))
    svc._transfers = AsyncMock()
    svc._transfers.list_banks = AsyncMock(return_value=[
        GatewayBank(code="044", name="Access Bank"), GatewayBank(code="058", name="Guaranty Trust Bank"),
    ])
    svc._transfers.resolve_account = AsyncMock(return_value=None if resolved is None else GatewayAccount(
        bank_code="058", account_number="0123456789", account_name=resolved,
    ))
    svc._gateways = MagicMock()
    svc._gateways.transfer_platform = MagicMock(return_value=platform)
    svc._gateways.transfers = MagicMock(return_value=svc._transfers)
    return svc


class TestBanks:
    async def test_banks_come_from_the_gateway_new_accounts_resolve_with(self):
        svc = _service()

        banks = await svc.list_banks()

        assert [b.code for b in banks] == ["044", "058"]
        svc._gateways.transfers.assert_called_with(IntegratedPlatform.PAYSTACK)
        svc._transfers.list_banks.assert_awaited_once_with(TransactionCurrency.NGN)

    async def test_the_bank_list_is_fetched_once_and_reused(self):
        svc = _service()

        await svc.list_banks()
        await svc.list_banks()

        assert svc._transfers.list_banks.await_count == 1


class TestResolve:
    async def test_the_name_is_the_one_the_bank_holds(self):
        resolved = await _service().resolve(ResolveBankAccountDto(bank_code="058", account_number="0123456789"))

        assert (resolved.bank_code, resolved.bank_name, resolved.account_name) == (
            "058", "Guaranty Trust Bank", "ADA OBI",
        )

    async def test_a_bank_not_on_the_gateways_list_is_refused_before_asking_it(self):
        svc = _service()

        with pytest.raises(ValidationException):
            await svc.resolve(ResolveBankAccountDto(bank_code="999", account_number="0123456789"))
        svc._transfers.resolve_account.assert_not_called()

    async def test_an_account_the_bank_does_not_know_is_refused(self):
        with pytest.raises(ValidationException):
            await _service(resolved=None).resolve(ResolveBankAccountDto(bank_code="058", account_number="0123456789"))

    @pytest.mark.parametrize("number", ["123", "01234567890", "01234abcde"])
    def test_an_account_number_must_be_a_ten_digit_nuban(self, number):
        with pytest.raises(ValueError):
            ResolveBankAccountDto(bank_code="058", account_number=number)


class TestAdd:
    async def test_it_stores_the_bank_held_name_and_the_resolving_gateway(self):
        svc = _service()

        account = await svc.add("a-1", AddBankAccountDto(bank_code="058", account_number="0123456789"))

        dto = svc._bank_account_repo.create_return_model.call_args.args[0]
        assert (dto.bank_code, dto.bank_name, dto.account_name, dto.provider) == (
            "058", "Guaranty Trust Bank", "ADA OBI", IntegratedPlatform.PAYSTACK.value,
        )
        assert account.is_default is True  # the first account becomes the default

    async def test_under_the_stub_the_account_carries_no_gateway(self):
        svc = _service(platform=None)

        await svc.add("a-1", AddBankAccountDto(bank_code="058", account_number="0123456789"))

        assert svc._bank_account_repo.create_return_model.call_args.args[0].provider is None

    async def test_the_same_account_is_not_saved_twice(self):
        existing = SimpleNamespace(id="ba-0", bank_code="058", account_number="0123456789", is_default=True, deleted=False)
        svc = _service(existing=[existing])

        with pytest.raises(ValidationException):
            await svc.add("a-1", AddBankAccountDto(bank_code="058", account_number="0123456789"))
        svc._bank_account_repo.create_return_model.assert_not_called()


class TestOwnership:
    async def test_another_agents_account_is_not_found(self):
        svc = _service()
        svc._bank_account_repo.get_model = AsyncMock(return_value=SimpleNamespace(
            id="ba-1", agent_id="a-2", deleted=False,
        ))

        with pytest.raises(ResourceNotFoundException):
            await svc.get_owned("a-1", "ba-1")
