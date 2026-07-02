"""Property service (PRD §4.3)."""
from __future__ import annotations

from kink import inject

from main.app.domain.property.models import (
    CreatePropertyDto,
    Property,
    PropertyInputDto,
    UpdatePropertyDto,
)
from main.app.domain.property.repo import PropertyRepo
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import ResourceNotFoundException


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class PropertyService:
    def __init__(self, property_repo: PropertyRepo):
        self._repo = property_repo

    async def create(self, customer_id: str, dto: PropertyInputDto) -> Property:
        return await self._repo.create_return_model(CreatePropertyDto(
            customer_id=customer_id,
            property_type=dto.property_type,
            address=dto.address,
            landmark=dto.landmark,
            state=dto.state,
            lga=dto.lga,
            latitude=dto.latitude,
            longitude=dto.longitude,
            place_id=dto.place_id,
            details=dto.details,
            seller=dto.seller.model_dump() if dto.seller else None,
            documents=dto.documents,
        ))

    async def update(self, property_id: str, dto: PropertyInputDto) -> Property:
        existing = await self._repo.get_model(property_id)
        if not existing:
            raise ResourceNotFoundException(resource="property")
        await self._repo.update(property_id, UpdatePropertyDto(
            property_type=dto.property_type.value if dto.property_type else None,
            address=dto.address,
            landmark=dto.landmark,
            state=dto.state,
            lga=dto.lga,
            latitude=dto.latitude,
            longitude=dto.longitude,
            place_id=dto.place_id,
            details=dto.details,
            seller=dto.seller.model_dump() if dto.seller else None,
            documents=dto.documents,
        ))
        return await self._repo.get_model(property_id)

    async def get(self, property_id: str) -> Property:
        existing = await self._repo.get_model(property_id)
        if not existing:
            raise ResourceNotFoundException(resource="property")
        return existing
