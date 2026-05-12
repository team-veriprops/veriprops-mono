from typing import Type

from kink import inject
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.verification.dispute.models import (
    Dispute, DisputeResolution,
    CreateDisputeDto, UpdateDisputeDto, QueryDisputeDto, SearchDisputeDto,
    CreateDisputeResolutionDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class DisputeRepo(GenericRepo[
    Dispute, CreateDisputeDto, UpdateDisputeDto, QueryDisputeDto, SearchDisputeDto,
]):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[Dispute] = Dispute,
        query_dto: Type[QueryDisputeDto] = QueryDisputeDto,
    ):
        super().__init__(db, model, query_dto)


@inject
class DisputeResolutionRepo(GenericRepo[
    DisputeResolution, CreateDisputeResolutionDto, CreateDisputeResolutionDto,
    QueryDisputeDto, SearchDisputeDto,
]):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[DisputeResolution] = DisputeResolution,
        query_dto: Type[QueryDisputeDto] = QueryDisputeDto,
    ):
        super().__init__(db, model, query_dto)
