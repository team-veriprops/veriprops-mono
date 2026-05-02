from typing import Type

from kink import inject
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.verification.property.models import (
    CreatePropertyDto,
    Property,
    QueryPropertyDto,
    SearchPropertyDto,
    UpdatePropertyDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class PropertyRepo(
    GenericRepo[
        Property,
        CreatePropertyDto,
        UpdatePropertyDto,
        QueryPropertyDto,
        SearchPropertyDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[Property] = Property,
        query_dto: Type[QueryPropertyDto] = QueryPropertyDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db
