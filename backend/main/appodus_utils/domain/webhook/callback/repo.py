from typing import Type, Optional

from kink import inject
from sqlalchemy import and_, literal
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.config.settings import IntegratedPlatform
from main.app.domain.webhook.callback.model import Callback, CreateCallbackDto, UpdateCallbackDto, QueryCallbackDto, \
    SearchCallbackDto
from main.app.domain.webhook.callback.model import CallbackType
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
        try:
            callbacks = self._build_query_for__by_platform_event_type_and_external_id(
                platform=platform,
                event_type=event_type,
                external_id=external_id
            ).first()

            return self._build_row_response(callbacks)
        except Exception as exc:
            raise exc

    async def exists_by_platform_event_type_and_external_id(self,
                                                         platform: IntegratedPlatform,
                                                         event_type: CallbackType,
                                                         external_id: str) -> bool:
        return self._session.query(literal(True)).filter(
            self._build_query_for__by_platform_event_type_and_external_id(
                platform=platform,
                event_type=event_type,
                external_id=external_id
            ).exists()).scalar()

    def _build_query_for__by_platform_event_type_and_external_id(self,
                                                         platform: IntegratedPlatform,
                                                         event_type: CallbackType,
                                                         external_id: str):
        return self._session.query(self._model).filter(
                and_(self._model.deleted == False,
                     and_(self._model.platform == platform,
                          and_(self._model.handled == False,
                               and_(self._model.event_type == event_type, self._model.external_id == external_id))))
            )
