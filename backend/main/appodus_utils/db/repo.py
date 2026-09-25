import enum
import re
import uuid
from typing import Any, Dict, Generic, Iterable, List, Optional, Tuple, Type, Union


from main.appodus_utils import Utils
from main.appodus_utils.db.db_utils import DbUtils
from main.appodus_utils.db.session import get_db_session_from_context
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import InvalidResourceStateException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import ColumnElement, Index, literal, select, func, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from main.appodus_utils.db.models import (
    Page, ModelType, CreateSchemaType, UpdateSchemaType,
    QuerySchemaType, SearchSchemaType, SuccessResponse
)


def _plain(value: Any) -> Any:
    """An enum member as the value its column stores; anything else unchanged."""
    return value.value if isinstance(value, enum.Enum) else value


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

    async def _flush_pending(self) -> None:
        """Write the session's pending edits before a statement that reloads rows.

        Sessions run with autoflush off, and `populate_existing` replaces a loaded row with the
        database's copy — so an edit made in memory just before (a status set on the same row a
        moment earlier) would be silently discarded. Flushing first keeps it.
        """
        await self._session.flush()

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


    async def get_all(self, search_dto: SearchSchemaType) -> List[ModelType]:
        rows, _, _, _, lean = await self._search_rows(search_dto)
        return rows

    # @transactional()
    async def get_by_criterion(self, search_dto: SearchSchemaType) -> List[QuerySchemaType]:
        rows, _, _, _, lean = await self._search_rows(search_dto)
        return self._db_utils.build_rows_response(rows, lean)

    async def get_even_soft_deleted(self, _id: Union[str, uuid.UUID], query_fields: Optional[str] = None) -> Optional[
        SuccessResponse[QuerySchemaType]]:
        row, lean = await self._get_model_by_id(_id, query_fields, include_deleted=True)

        return self._db_utils.build_row_response(row, lean)

    async def to_query_dto(self, row: ModelType):
        return self._db_utils.build_row_response(row=row, return_success_response_obj=False)

    async def get_page(self, search_dto: SearchSchemaType) -> Page[QuerySchemaType]:
        rows, criterion, page, page_size, lean = await self._search_rows(search_dto)

        total_stmt = select(func.count(self._model.id)).where(*criterion)
        total = await self._session.scalar(total_stmt)

        response_rows = self._db_utils.build_rows_response(rows, lean)

        return self._db_utils.build_page(response_rows, total, page, page_size)


    @transactional()
    async def create_return_model(self, obj_in: CreateSchemaType) -> ModelType:
        obj_in_data = obj_in.model_dump(by_alias=False)
        db_obj = self._model(**obj_in_data)
        db_obj.id = self._ensure_uuid(db_obj.id)
        db_obj.version = 1
        db_obj.date_created = Utils.datetime_now()
        self._session.add(db_obj)
        return db_obj

    def _unique_index_target(self, name: str) -> Tuple[List[str], Optional[ColumnElement[bool]]]:
        """Columns and predicate of the model's unique index *name*, for an ON CONFLICT target.

        Read off the model's own declaration (`live_unique_index`), which the migration is
        pinned to, so the target always matches the index Postgres holds. Postgres only accepts
        a partial-index target whose predicate it can prove matches, and a hand-written
        equivalent (`deleted IS false` for `deleted = false`) fails that proof.
        """
        for index in self._model.__table__.indexes:
            if isinstance(index, Index) and index.name == name and index.unique:
                return [c.name for c in index.columns], index.dialect_options["postgresql"]["where"]
        raise ValueError(f"{self._table_name} declares no unique index named {name!r}")

    async def insert_or_get(
            self,
            values: Dict[str, Any],
            conflict_columns: Optional[List[str]] = None,
            *,
            unique_index: Optional[str] = None,
    ) -> Tuple[ModelType, bool]:
        """Create the row, or return the one already holding its unique key — race-free.

        Select-then-insert lets two concurrent requests both find nothing and both insert,
        and the loser's commit then violates the unique constraint (a 500). Here the insert
        is `INSERT … ON CONFLICT DO NOTHING RETURNING`: Postgres makes a concurrent attempt
        wait for the winner and then yield, and the winner's row is read back.

        Name the key either by *conflict_columns* (a full unique constraint or primary key)
        or by *unique_index* (a partial unique index declared on the model, e.g. one over
        live rows). Returns ``(row, created)``.
        """
        conflict_columns, conflict_where = self._conflict_target(conflict_columns, unique_index)
        stmt = (
            pg_insert(self._model)
            .values(**self._new_row(values))
            .on_conflict_do_nothing(index_elements=conflict_columns, index_where=conflict_where)
            .returning(self._model)
        )
        created = (await self._session.execute(stmt)).scalar_one_or_none()
        if created is not None:
            return created, True

        existing = select(self._model).where(
            *[getattr(self._model, column) == values[column] for column in conflict_columns]
        )
        if conflict_where is not None:
            existing = existing.where(conflict_where)
        return (await self._session.execute(existing)).scalars().first(), False

    async def upsert(
            self,
            values: Dict[str, Any],
            update_columns: List[str],
            conflict_columns: Optional[List[str]] = None,
            *,
            unique_index: Optional[str] = None,
    ) -> ModelType:
        """Create the row, or overwrite *update_columns* on the one holding its key, in one statement.

        `INSERT … ON CONFLICT DO UPDATE … RETURNING`. Unlike read-then-write, there is no
        window in which two concurrent requests both find nothing and both insert. The key
        is named as in `insert_or_get`. The row's version and `date_updated` move on update,
        and an instance of it already loaded in this session is refreshed.
        """
        conflict_columns, conflict_where = self._conflict_target(conflict_columns, unique_index)
        await self._flush_pending()
        stmt = pg_insert(self._model).values(**self._new_row(values))
        set_: Dict[str, Any] = {column: stmt.excluded[column] for column in update_columns}
        set_["date_updated"] = Utils.datetime_now()
        set_["version"] = self._model.version + 1
        stmt = (
            stmt.on_conflict_do_update(
                index_elements=conflict_columns, index_where=conflict_where, set_=set_,
            )
            .returning(self._model)
            .execution_options(populate_existing=True)
        )
        return (await self._session.execute(stmt)).scalar_one()

    async def claim_transition(
            self,
            _id: Union[str, uuid.UUID],
            from_statuses: Iterable[Any],
            to_status: Any = None,
            *,
            status_column: str = "status",
            expect: Optional[Dict[str, Any]] = None,
            increments: Optional[Dict[str, int]] = None,
            **values: Any,
    ) -> Optional[ModelType]:
        """Move the row out of one of *from_statuses*, only if it is still there — race-free.

        Read-check-write lets two concurrent requests both see REQUESTED and both approve,
        refund or pay out. Here the check is the `WHERE` of one `UPDATE … RETURNING`:
        Postgres makes a concurrent claim wait for the winner and then re-check the row, so
        exactly one caller gets the row back. The others get None and must not repeat what
        follows the move (money, events, notifications).

        *to_status* may be omitted to update the row only while it is still in a status
        (an adjustment allowed on an undecided payout). *expect* pins other columns the
        decision was made on (`None` means IS NULL). *increments* add to counters in SQL.
        *values* are written as given. Enum members are stored as their values.
        """
        column = getattr(self._model, status_column)
        conditions = [
            self._model.id == self._ensure_uuid(_id),
            self._model.deleted.is_(False),
            column.in_([_plain(status) for status in from_statuses]),
        ]
        for name, expected in (expect or {}).items():
            attribute = getattr(self._model, name)
            conditions.append(attribute.is_(None) if expected is None else attribute == _plain(expected))

        set_: Dict[str, Any] = {name: _plain(value) for name, value in values.items()}
        for name, step in (increments or {}).items():
            set_[name] = func.coalesce(getattr(self._model, name), 0) + step
        if to_status is not None:
            set_[status_column] = _plain(to_status)
        set_["version"] = self._model.version + 1
        set_["date_updated"] = Utils.datetime_now()

        await self._flush_pending()
        stmt = (
            update(self._model)
            .where(*conditions)
            .values(**set_)
            .returning(self._model)
            .execution_options(populate_existing=True, synchronize_session=False)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def lock_model(self, _id: Union[str, uuid.UUID]) -> Optional[ModelType]:
        """The live row, locked `FOR UPDATE` until this transaction ends.

        For a decision taken over several steps whose end state is derived, not known up
        front (a release computes COMPLETED from its tasks), so no single claim can express
        it. A concurrent decision on the same row waits here, then reads what the first one
        committed.
        """
        await self._flush_pending()
        stmt = (
            select(self._model)
            .where(self._model.id == self._ensure_uuid(_id), self._model.deleted.is_(False))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    def _conflict_target(
            self, conflict_columns: Optional[List[str]], unique_index: Optional[str],
    ) -> Tuple[List[str], Optional[ColumnElement[bool]]]:
        if unique_index is not None:
            return self._unique_index_target(unique_index)
        if not conflict_columns:
            raise ValueError("A conflict target needs conflict_columns or unique_index")
        return conflict_columns, None

    @staticmethod
    def _new_row(values: Dict[str, Any]) -> Dict[str, Any]:
        """*values* plus the base columns a plain create would set."""
        return {
            "id": Utils.generate_uuid(),
            "version": 1,
            "date_created": Utils.datetime_now(),
            "deleted": False,
            **values,
        }

    # @handle_exceptions
    @transactional()
    async def create(self, obj_in: CreateSchemaType) -> SuccessResponse[QuerySchemaType]:
        db_obj = await self.create_return_model(obj_in=obj_in)
        return self._db_utils.build_row_response(db_obj)

    # @handle_exceptions
    @transactional()
    async def create_all(self, objs_in: List[CreateSchemaType]) -> List[QuerySchemaType]:
        db_objs = []
        for obj_in in objs_in:
            obj_in_data = obj_in.model_dump(by_alias=False)
            db_obj = self._model(**obj_in_data)
            db_obj.id = self._ensure_uuid(db_obj.id)
            db_obj.version = 1
            self._session.add(db_obj)
            db_objs.append(db_obj)

        return self._db_utils.build_rows_response(db_objs)

    # @handle_exceptions
    @transactional()
    async def update_return_model(self, _id: Union[str, uuid.UUID], obj_in: Union[UpdateSchemaType, Dict[str, Any]]) -> Optional[ModelType]:
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
                    except AttributeError:
                        raise AttributeError(f"Invalid column '{field}' for table '{self._table_name}'")

            old_version = update_dict.get("version")

            if old_version and old_version != db_obj.version:
                raise InvalidResourceStateException(f"'{self._table_name}'")

            if not old_version:
                old_version = db_obj.version

            new_version = int(old_version or 0) + 1

            db_obj.version = new_version
            db_obj.date_updated = Utils.datetime_now()
            self._session.add(db_obj)
        return db_obj

    @transactional()
    async def update(self, _id: Union[str, uuid.UUID], obj_in: Union[UpdateSchemaType, Dict[str, Any]]) -> Optional[
        SuccessResponse[QuerySchemaType]]:
        db_obj = await self.update_return_model(_id=_id, obj_in=obj_in)

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
            return Utils.generate_uuid()
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
        # order_by / query_fields are server-only controls (InternalPageRequest). A
        # client-facing PageRequest DTO lacks them — default to no explicit ordering /
        # full-row select rather than trusting wire input.
        order_by_columns = self._db_utils.parse_order_by_clause(getattr(search_dto, 'order_by', None))
        query_fields = getattr(search_dto, 'query_fields', None)
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
