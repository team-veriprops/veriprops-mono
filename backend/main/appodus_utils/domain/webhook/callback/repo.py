from typing import Type, Optional

from kink import inject
from sqlalchemy import literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.config.settings import IntegratedPlatform
from main.appodus_utils.domain.webhook.callback.model import Callback, CreateCallbackDto, UpdateCallbackDto, QueryCallbackDto, \
    SearchCallbackDto
from main.appodus_utils.domain.webhook.callback.model import CallbackType
from main.appodus_utils.db.repo import GenericRepo


@inject
class CallbackRepo(GenericRepo[Callback, CreateCallbackDto, UpdateCallbackDto, QueryCallbackDto, SearchCallbackDto]):
    def __init__(self, db: AsyncSession, model: Type[Callback] = Callback,
                 query_dto: Type[QueryCallbackDto] = QueryCallbackDto):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_by_platform_event_type_and_external_id(self,
                                                         platform: IntegratedPlatform,
                                                         event_type: CallbackType,
                                                         external_id: str) -> Optional[QueryCallbackDto]:
        stmt = select(self._model).where(
            *self._unhandled_event_criterion(platform, event_type, external_id)
        ).limit(1)
        row = (await self._session.execute(stmt)).scalars().first()
        return await self.to_query_dto(row) if row is not None else None

    async def exists_by_platform_event_type_and_external_id(self,
                                                            platform: IntegratedPlatform,
                                                            event_type: CallbackType,
                                                            external_id: str) -> bool:
        stmt = select(literal(True)).where(
            *self._unhandled_event_criterion(platform, event_type, external_id)
        ).limit(1)
        return (await self._session.execute(stmt)).scalar() is not None

    def _unhandled_event_criterion(self,
                                   platform: IntegratedPlatform,
                                   event_type: CallbackType,
                                   external_id: str) -> list:
        """A live callback for this provider event that has not been handled yet."""
        return [
            self._model.deleted.is_(False),
            self._model.handled.is_(False),
            self._model.platform == platform,
            self._model.event_type == event_type,
            self._model.external_id == external_id,
        ]
