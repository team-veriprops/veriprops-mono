"""Re-check repo — S44."""
from __future__ import annotations

from typing import Type

from kink import inject
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.verification.recheck.models import (
    RecheckRequest,
    CreateRecheckRequestDto,
    UpdateRecheckRequestDto,
    QueryRecheckRequestDto,
    SearchRecheckRequestDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class RecheckRequestRepo(GenericRepo[
    RecheckRequest,
    CreateRecheckRequestDto,
    UpdateRecheckRequestDto,
    QueryRecheckRequestDto,
    SearchRecheckRequestDto,
]):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[RecheckRequest] = RecheckRequest,
        query_dto: Type[QueryRecheckRequestDto] = QueryRecheckRequestDto,
    ):
        super().__init__(db, model, query_dto)
