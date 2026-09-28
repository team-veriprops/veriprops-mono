"""Agent bank account domain (PRD §15.1).

A stored payout beneficiary, and the only place a payout can go. An agent picks a bank from
the gateway's own list and gives an account number; the name stored is the one the bank
returns for that pair, never one the agent typed, and the account remembers which gateway
resolved it (bank codes are only meaningful to the gateway whose list they came from). An
agent may keep several and mark one default. No sensitive verification data is held — bank
name and code, account number, account name only.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field
from sqlalchemy import Boolean, Column, String

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, InternalPageRequest

# A Nigerian NUBAN account number: exactly ten digits.
NUBAN_PATTERN = r"^\d{10}$"


# ─── ORM ──────────────────────────────────────────────────────────

class AgentBankAccount(BaseEntity):
    __tablename__ = "agent_bank_accounts"

    agent_id = Column(String(36), nullable=False, index=True)
    bank_name = Column(String(128), nullable=False)
    account_number = Column(String(32), nullable=False)
    account_name = Column(String(128), nullable=False)
    is_default = Column(Boolean, nullable=False, default=False)
    # The gateway's code for the bank, and the gateway that resolved the account (None under
    # the stub). An account saved before resolution existed has neither and cannot be paid.
    bank_code = Column(String(16), nullable=True)
    provider = Column(String(32), nullable=True)


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateBankAccountDto(Object):
    agent_id: str
    bank_name: str
    bank_code: str
    provider: Optional[str] = None
    account_number: str
    account_name: str
    is_default: bool = False


class UpdateBankAccountDto(Object):
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    account_name: Optional[str] = None
    is_default: Optional[bool] = None


class QueryBankAccountDto(BaseQueryDto):
    agent_id: Optional[str] = None


class SearchBankAccountDto(InternalPageRequest, BaseQueryDto):
    agent_id: Optional[str] = None


class ResolveBankAccountDto(Object):
    """Ask the bank whose account this is, before saving it."""

    bank_code: str = Field(..., min_length=1, max_length=16)
    account_number: str = Field(..., pattern=NUBAN_PATTERN)


class AddBankAccountDto(ResolveBankAccountDto):
    """Save a beneficiary. The name is resolved again server-side, never taken from the client."""

    is_default: bool = False


class BankDto(Object):
    code: str
    name: str


class ResolvedBankAccountDto(Object):
    """An account as the bank holds it."""

    bank_code: str
    bank_name: str
    account_number: str
    account_name: str


class BankAccountDto(Object):
    id: str
    bank_name: str
    bank_code: Optional[str] = None
    account_number: str
    account_name: str
    is_default: bool
    date_created: datetime
