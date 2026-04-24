import re
import uuid
from typing import Any, Dict, Generic, List, Optional, Type, Union


from main.appodus_utils import Utils
from main.appodus_utils.db.db_utils import DbUtils
from main.appodus_utils.db.session import get_db_session_from_context
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import InvalidResourceStateException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import literal, select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from main.appodus_utils.db.models import (
    Page, ModelType, CreateSchemaType, UpdateSchemaType,
    QuerySchemaType, SearchSchemaType, SuccessResponse
)


@decorate_all_methods(method_trace_logger)
class GenericRepo(Generic[ModelType, CreateSchemaType, UpdateSchemaType, QuerySchemaType, SearchSchemaType]):
    def __init__(self, db: AsyncSession, model: Type[ModelType], query_qto: Type[QuerySchemaType]):
        """
        :param db: SQLAlchemy async session
        :param model: SQLAlchemy model class
        :param query_qto: Query transfer object class
        """
        self._db = db
        self._model = model
        self._query_qto = query_qto
        self._table_name = self._model.__tablename__
        self._db_utils = DbUtils(model=model, query_qto=query_qto)

    @property
    def _session(self) -> AsyncSession:
        return get_db_session_from_context()

    async def exists_by_id(self, _id: str) -> bool:
        _id: uuid.UUID = self._ensure_uuid(_id)
        stmt = select(literal(True)).where(
            self._model.deleted.is_(False), self._model.id == _id
        )
        result = await self._session.execute(stmt)
        return result.scalar() is not None

    async def exists_by_criterion(self, search_dto: SearchSchemaType) -> bool:
        criterion = self._db_utils.build_search_criterion(search_dto)
        stmt = select(literal(True)).where(*criterion)
        result = await self._session.execute(stmt)
        return result.scalar() is not None

    async def get(self, _id: Any, query_fields: str = None) -> Optional[SuccessResponse[QuerySchemaType]]:
        row = await self.get_model(_id, query_fields)

        return self._db_utils.build_row_response(row)

    async def get_model(self, _id: Union[str, uuid.UUID], query_fields: Optional[str] = None) -> Optional[ModelType]:
        row, _ =  await self._get_model_by_id(_id, query_fields, include_deleted=False)

        return row

    # @transactional()
    async def get_by_criterion(self, search_dto: SearchSchemaType) -> List[QuerySchemaType]:
        rows, _, _, _, lean = await self._search_rows(search_dto)
        return self._db_utils.build_rows_response(rows, lean)

    async def get_even_soft_deleted(self, _id: Union[str, uuid.UUID], query_fields: Optional[str] = None) -> Optional[
        SuccessResponse[QuerySchemaType]]:
        row, lean = await self._get_model_by_id(_id, query_fields, include_deleted=True)

        return self._db_utils.build_row_response(row, lean)

    async def get_page(self, search_dto: SearchSchemaType) -> Page[QuerySchemaType]:
        rows, criterion, page, page_size, lean = await self._search_rows(search_dto)

        total_stmt = select(func.count(self._model.id)).where(*criterion)
        total = await self._session.scalar(total_stmt)

        response_rows = self._db_utils.build_rows_response(rows, lean)

        return self._db_utils.build_page(response_rows, total, page, page_size)

    # @handle_exceptions
    @transactional()
    async def create(self, obj_in: CreateSchemaType) -> SuccessResponse[QuerySchemaType]:
        obj_in_data = jsonable_encoder(obj_in, by_alias=False)
        db_obj = self._model(**obj_in_data)
        db_obj.id = self._ensure_uuid(db_obj.id)
        db_obj.version = 1
        self._session.add(db_obj)
        return self._db_utils.build_row_response(db_obj)

    # @handle_exceptions
    @transactional()
    async def create_all(self, objs_in: List[CreateSchemaType]) -> List[QuerySchemaType]:
        db_objs = []
        for obj_in in objs_in:
            obj_in_data = jsonable_encoder(obj_in, by_alias=False)
            db_obj = self._model(**obj_in_data)
            db_obj.id = self._ensure_uuid(db_obj.id)
            db_obj.version = 1
            self._session.add(db_obj)
            db_objs.append(db_obj)

        return self._db_utils.build_rows_response(db_objs)

    # @handle_exceptions
    @transactional()
    async def update(self, _id: Union[str, uuid.UUID], obj_in: Union[UpdateSchemaType, Dict[str, Any]]) -> Optional[
        SuccessResponse[QuerySchemaType]]:
        db_obj = await self._get(_id)
        if db_obj and obj_in:
            db_obj_data = jsonable_encoder(db_obj, by_alias=False)
            update_dict = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True,
                                                                                    exclude_none=True)
            update_data = jsonable_encoder(update_dict, by_alias=False)
            update_data = Utils.obj_time_to_str(update_data)

            for field in db_obj_data:
                if field in update_data:
                    try:
                        converted_field = self._convert_camel_case_to_underscore_separated(field)
                        setattr(db_obj, converted_field or field, update_data[field])
                    except AttributeError as e:
                        raise AttributeError(f"Invalid column '{field}' for table '{self._table_name}'")

            old_version = update_dict.get("version")

            if old_version and old_version != db_obj.version:
                raise InvalidResourceStateException(f"'{self._table_name}'")

            if not old_version:
                old_version = db_obj.version

            new_version = old_version + 1

            db_obj.version = new_version
            self._session.add(db_obj)
        return self._db_utils.build_row_response(db_obj)

    # @handle_exceptions
    @transactional()
    async def soft_delete_by_criterion(self, search_dto: SearchSchemaType) -> int:
        criterion = self._db_utils.build_search_criterion(search_dto)
        count_stmt = select(func.count(self._model.id)).where(*criterion)
        count_result = await self._session.execute(count_stmt)
        count_before = count_result.scalar()

        await self._session.execute(
            update(self._model)
            .where(*criterion)
            .values(deleted=True, date_deleted=Utils.datetime_now())
        )

        return count_before

    # @handle_exceptions
    @transactional()
    async def soft_delete(self, _id: Any) -> Optional[SuccessResponse[QuerySchemaType]]:
        db_obj = await self._get(_id)
        return await self.soft_delete_obj(db_obj)

    # @handle_exceptions
    @transactional()
    async def soft_delete_obj(self, obj: ModelType) -> Optional[SuccessResponse[QuerySchemaType]]:
        if obj:
            obj.deleted = True
            obj.date_deleted = Utils.datetime_now()
            await self._session.merge(obj)
        return self._db_utils.build_row_response(obj)

    @transactional()
    async def soft_delete_all(self, _ids: List[Any]) -> bool:
        for _id in _ids:
            await self.soft_delete(_id)
        return True

    @transactional()
    async def soft_delete_all_obj(self, objs: List[QuerySchemaType]) -> bool:
        for obj in objs:
            await self.soft_delete_obj(obj)

        return True

    @transactional()
    async def hard_delete(self, _id: str) -> bool:

        db_obj = await self._get(_id)
        if db_obj:
            await self._session.delete(db_obj)

        return True

    @staticmethod
    def _ensure_uuid(_id: Union[str, uuid.UUID]) -> uuid.UUID:
        if not _id:
            return uuid.uuid4()
        return Utils.hex_to_uuid(_id) if isinstance(_id, str) else _id

    async def _get(self, _id: Union[str, uuid.UUID]) -> Optional[ModelType]:
        _id = self._ensure_uuid(_id)
        stmt = select(self._model).where(self._model.id == _id, self._model.deleted.is_(False))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    def _convert_camel_case_to_underscore_separated(name: str) -> str:
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    async def _get_model_by_id(self, _id: Union[str, uuid.UUID], query_fields: Optional[str],
                               include_deleted: bool = False) -> tuple[Optional[ModelType], bool]:
        _id = self._ensure_uuid(_id)
        row = None
        lean = bool(query_fields)
        if lean:
            select_columns = self._db_utils.parse_selected_columns(query_fields)
            if select_columns:
                stmt = select(*select_columns).where(self._model.id == _id)
                if not include_deleted:
                    stmt.where(self._model.deleted.is_(False))
                result = await self._session.execute(stmt)
                row = self._db_utils.create_entity_model(query_fields, result.first())
        else:
            stmt = select(self._model).where(self._model.id == _id)
            if not include_deleted:
                stmt = stmt.where(self._model.deleted.is_(False))
            result = await self._session.execute(stmt)
            row = result.scalar_one_or_none()
        return row, lean

    async def _search_rows(self, search_dto: SearchSchemaType) -> tuple[list, list, int, int, bool]:
        page = search_dto.page
        page_size = search_dto.page_size
        offset = page * page_size
        criterion = self._db_utils.build_search_criterion(search_dto)
        order_by_columns = self._db_utils.parse_order_by_clause(search_dto.order_by)
        query_fields = search_dto.query_fields
        lean = bool(query_fields)
        if lean:
            select_columns = self._db_utils.parse_selected_columns(query_fields)
            if len(select_columns) <= 0:
                rows = []
            else:
                stmt = (select(*select_columns)
                        .where(*criterion)
                        .order_by(*order_by_columns)
                        .offset(offset)
                        .limit(page_size))
                results = await self._session.execute(stmt)
                rows: List[ModelType] = []
                for result in results.all():
                    row = self._db_utils.create_entity_model(query_fields, result)
                    rows.append(row)
        else:
            stmt = (select(self._model)
                    .where(*criterion)
                    .order_by(*order_by_columns)
                    .offset(offset)
                    .limit(page_size))
            result = await self._session.execute(stmt)
            rows = result.scalars().all()

        return rows, criterion, page, page_size, lean
