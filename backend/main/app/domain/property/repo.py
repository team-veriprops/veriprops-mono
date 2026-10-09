from typing import Optional, Type

from kink import inject
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.property.models import (
    CreatePropertyDto,
    Property,
    QueryPropertyDto,
    SearchPropertyDto,
    UpdatePropertyDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class PropertyRepo(
    GenericRepo[Property, CreatePropertyDto, UpdatePropertyDto, QueryPropertyDto, SearchPropertyDto]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[Property] = Property,
        query_dto: Type[QueryPropertyDto] = QueryPropertyDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def state_of(self, property_id: Optional[str]) -> Optional[str]:
        """The property's state, for matching an agent's coverage (None when unknown)."""
        if not property_id:
            return None
        prop = await self.get_model(property_id)
        return prop.state if prop is not None else None
