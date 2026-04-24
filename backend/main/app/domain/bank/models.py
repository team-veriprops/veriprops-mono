from typing import Optional

from main.appodus_utils import Object
from sqlalchemy import Column, String

from main.appodus_utils import BaseEntity, PageRequest, BaseQueryDto



class Bank(BaseEntity):
    __tablename__ = 'banks'
    name = Column(String, nullable=False)
    short_name = Column(String)
    code = Column(String)
    status = Column(String(12), nullable=False)
    country_code = Column(String, nullable=False)


class BankBaseDto(Object):
    name: str
    short_name: str
    code: str
    country_code: str


class CreateBankDto(BankBaseDto):
    status: str


class UpdateBankDto(BankBaseDto):
    pass


class _UpdateBankDto(Object):
    status: Optional[str] = None
    name: Optional[str] = None


class SearchBankDto(PageRequest, BaseQueryDto):
    name: Optional[str] = None
    short_name: Optional[str] = None
    country_code: Optional[str] = None
    status: Optional[str] = None
    code: Optional[str] = None


class QueryBankDto(BankBaseDto, BaseQueryDto):
    status: Optional[str] = None
