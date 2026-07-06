"""Agent bank account domain (PRD §15.1).

A stored payout beneficiary. An agent may keep several and mark one default; a one-time
entry at withdrawal time bypasses this store (snapshot copied onto the payout instead).
No sensitive verification data is held — bank name / account number / account name only.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, String

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest


# ─── ORM ──────────────────────────────────────────────────────────

class AgentBankAccount(BaseEntity):
    __tablename__ = "agent_bank_accounts"

    agent_id = Column(String(36), nullable=False, index=True)
    bank_name = Column(String(128), nullable=False)
    account_number = Column(String(32), nullable=False)
    account_name = Column(String(128), nullable=False)
    is_default = Column(Boolean, nullable=False, default=False)


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateBankAccountDto(Object):
    agent_id: str
    bank_name: str
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


class SearchBankAccountDto(PageRequest, BaseQueryDto):
    agent_id: Optional[str] = None


class AddBankAccountDto(Object):
    """Agent request to store a beneficiary."""

    bank_name: str
    account_number: str
    account_name: str
    is_default: bool = False


class BankAccountDto(Object):
    id: str
    bank_name: str
    account_number: str
    account_name: str
    is_default: bool
    date_created: datetime
