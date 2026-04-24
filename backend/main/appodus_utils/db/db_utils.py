from logging import Logger
from typing import Type, List, Optional, Dict, Any, Union

from fastapi.encoders import jsonable_encoder
from kink import di
from sqlalchemy import Row

from main.appodus_utils import Utils
from main.appodus_utils.db.models import ModelType, QuerySchemaType, SearchSchemaType, Page, PaginationMeta, SuccessResponse
from main.appodus_utils.exception.exceptions import AppodusBaseException

logger: Logger = di['logger']


class DbUtils:
    def __init__(self, model: Type[ModelType], query_qto: Type[QuerySchemaType]):
        self._model = model
        self._query_qto = query_qto
        self._table_name = self._model.__tablename__

    def build_search_criterion(self, search_dto: SearchSchemaType) -> List:

        if not search_dto.deleted: # Ignore deleted by default
            search_dto.deleted = False

        where_conditions: List = []
        exclusion = {'platform', 'page', 'page_size', 'query_fields', 'exact_string_values', 'ocr', 'order_by', 'where'}
        exact_string_values = search_dto.exact_string_values

        if search_dto.where:
            w_exclusion, w_conditions = self._parse_where_conditions(search_dto)
            if w_exclusion:
                exclusion.update(w_exclusion)
            if w_conditions:
                where_conditions.append(w_conditions)

        search_dto_dict = search_dto.model_dump(
            exclude_none=True,
            exclude=exclusion
        )

        for field, value in search_dto_dict.items():
            column = getattr(self._model, field, None)
            if column is not None:
                if field == 'id':
                    value = Utils.remove_dash(value)

                where_conditions.append(column == value)

        return where_conditions

    def _parse_where_conditions(self, search_dto: SearchSchemaType) -> tuple[set, list]:
        condition_str: str = search_dto.where
        if not condition_str:
            return set(), []

        exclusion = set()
        conditions = []

        for cond in self._split_conditions(condition_str):
            field, op = self._parse_condition(cond)
            column = self._get_model_column(field)
            exclusion.add(field)

            raw_val = self._get_search_value(search_dto, field)
            raw_val = self._normalize_value(raw_val)

            conditions.append(self._build_condition(column, op, raw_val))

        return exclusion, conditions

    @staticmethod
    def _split_conditions(condition_str: str) -> list[str]:
        conditions = [cond.strip() for cond in condition_str.split(',') if cond.strip()]
        for cond in conditions:
            if ' ' not in cond:
                raise AppodusBaseException(f"Invalid value '{cond}' passed to where clause.")
        return conditions

    @staticmethod
    def _parse_condition(condition: str) -> tuple[str, str]:
        field, op = condition.rsplit(' ', 1)
        return field.strip(), op.strip().lower()

    def _get_model_column(self, field: str):
        column = getattr(self._model, field, None)
        if column is None:
            raise AppodusBaseException(f"Column name '{field}' not found in table {self._table_name}.")
        return column

    @staticmethod
    def _get_search_value(dto: SearchSchemaType, field: str):
        val = getattr(dto, field, None)
        if val is None:
            raise AppodusBaseException(f"No value passed for column '{field}' in where clause.")
        return val

    @staticmethod
    def _normalize_value(value):
        if isinstance(value, str):
            if (value.startswith("'") and value.endswith("'")) or (value.startswith('"') and value.endswith('"')):
                return value[1:-1]
        return value

    @staticmethod
    def _build_condition(column, op: str, value):
        match op:
            case "==":
                return column == value
            case "!=":
                return column != value
            case ">":
                return column > value
            case "<":
                return column < value
            case ">=":
                return column >= value
            case "<=":
                return column <= value
            case "like":
                return column.like(value)
            case "ilike":
                return column.ilike(value)
            case _:
                raise ValueError(f"Unsupported operator: {op}")

    def parse_selected_columns(self, columns_str):
        """
        Convert comma-separated column names to SQLAlchemy column objects.
        """
        if not columns_str:
            return [self._model]  # default to full table

        columns = []
        for col_name in columns_str.split(','):
            col_name = col_name.strip()
            if not col_name:
                continue
            col = getattr(self._model, col_name, None)
            if col is not None:
                columns.append(col)

        return columns if columns else [self._model]

    def parse_order_by_clause(self, order_by_str: str):
        """
        Parses a string like "age desc, name asc" into SQLAlchemy columns.
        """
        columns = []
        if not order_by_str:
            return columns

        for part in order_by_str.split(','):
            part = part.strip()
            if not part:
                continue

            # Split field and direction
            if ' ' in part:
                field, direction = part.rsplit(' ', 1)
                direction = direction.lower()
            else:
                field, direction = part, 'asc'

            column = getattr(self._model, field, None)
            if column is None:
                continue  # or raise error

            if direction == 'desc':
                columns.append(column.desc())
            else:
                columns.append(column.asc())

        return columns

    def create_entity_model(self, query_fields: str, result: Row[tuple[Any]]):
        """
        Maps the query result tuple to the model instance using the given comma-separated field list.

        Args:
            query_fields (str): Comma-separated field names (e.g., "id, name, age").
            result (tuple): The corresponding row data from a query.

        Returns:
            An instance of self._model with attributes set.

        Raises:
            AttributeError: If any field name is not valid for the model.
            ValueError: If number of fields doesn't match the number of result values.
        """
        logger.debug(f"Creating entity for table: {self._table_name}")
        logger.debug(f"Query fields: {query_fields}")
        logger.debug(f"Query result: {result}")

        row = self._model()
        fields = [f.strip() for f in query_fields.split(',') if f.strip()]

        if len(fields) != len(result):
            error_msg = (
                f"Field count ({len(fields)}) does not match result count ({len(result)}) "
                f"for table '{self._table_name}'"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        for field, value in zip(fields, result):
            if not hasattr(row, field):
                error_msg = f"Invalid column '{field}' for table '{self._table_name}'"
                logger.error(error_msg)
                raise AttributeError(error_msg)

            logger.debug(f"Setting attribute {field} = {value}")
            setattr(row, field, value)

        logger.debug(f"Created entity: {row}")
        return row

    def build_rows_response(self, rows: List[ModelType], lean: bool = False):
        response_rows: List[QuerySchemaType] = []
        for row in rows:
            response_rows.append(self.build_row_response(row=row, lean=lean, return_success_response_obj=False))
        return response_rows

    def build_row_response(self, row: Any, lean: bool = False, return_success_response_obj: bool = True) -> Optional[Union[QuerySchemaType, SuccessResponse[QuerySchemaType]]]:
        response = None

        if row:
            row_data = jsonable_encoder(row, by_alias=False)
            row_data['id'] = Utils.uuid_to_hex(row.id)
            if lean:
                response = self._query_qto.model_construct(**row_data)
            else:
                response = self._query_qto(**row_data)

            if return_success_response_obj:
                response = SuccessResponse(
                    data=response
                )

        return response

    @staticmethod
    def build_page(response_rows: List[QuerySchemaType], total: int, page: int, page_size: int):
        prev_page: Optional[int] = None if page == 0 else page - 1
        next_page: Optional[int] = None if total / page_size <= page + 1 else page + 1
        count = len(response_rows)
        meta = PaginationMeta(
            page=page,
            page_size=page_size,
            count=count,
            total=total,
            prev_page=prev_page,
            next_page=next_page,
        )

        return Page(
            items=response_rows,
            meta=meta,
        )

    def _get_tab_column(self, key: str):
        column = getattr(self._model, key, None)
        if not column:
            raise AppodusBaseException(f"Invalid column '{key}' for table '{self._table_name}'")
        return f'{self._table_name}.{key}'

    @staticmethod
    def _row_to_dict(row: Row) -> Dict[str, Any]:
        return row._asdict()
