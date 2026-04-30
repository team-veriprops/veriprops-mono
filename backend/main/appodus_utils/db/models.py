import uuid
from datetime import datetime
from typing import TypeVar, Optional, Generic, List, Union

from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import Column, Boolean, UUID, TIMESTAMP, Integer, String
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import declared_attr, DeclarativeBase

from main.appodus_utils import Utils


class AutoRepr:
    """
    Lightweight mixin that provides a helpful string representation
    for debugging and structured logs.

    Example:
        class User(AutoRepr):
            ...

        User(name="Kingsley", email="k@example.com")
        -> <User: {name='Kingsley', email='k@example.com'}>
    """

    def __repr__(self) -> str:
        items = (f"{key}={value!r}" for key, value in self.__dict__.items())
        return f"<{self.__class__.__name__}: {{{', '.join(items)}}}>"


def to_camel(field_name: str) -> str:
    """
    Convert a Python snake_case field name to camelCase.

    This function is used by Pydantic's `alias_generator` so our API can:

    - Keep Python code idiomatic with snake_case fields
    - Expose JSON payloads in camelCase (frontend-friendly)
    - Accept incoming requests in camelCase while mapping them
      correctly to snake_case model attributes

    Examples:
        >>> to_camel("first_name")
        'firstName'

        >>> to_camel("country_code")
        'countryCode'

        >>> to_camel("email")
        'email'

    Args:
        field_name:
            Internal Python field name in snake_case.

    Returns:
        camelCase representation of the field name.
    """
    parts = field_name.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


class CamelModel(BaseModel):
    """
    Base Pydantic model for all API DTOs.

    Provides automatic snake_case ↔ camelCase mapping.

    Why:
        Backend Python code should remain idiomatic (snake_case),
        while API contracts are typically camelCase for frontend/mobile clients.

    Behavior:
        Serialization:
            country_code -> countryCode

        Validation:
            Accepts:
                {"countryCode": "NG"}
            and maps to:
                model.country_code == "NG"

        Population by field name:
            Also accepts:
                {"country_code": "NG"}

    Extra fields:
        Unknown incoming fields are ignored rather than raising validation errors.
        This makes request handling more resilient to harmless client-side additions.

    Example:
        class UserDto(CamelModel):
            first_name: str
            phone_number: str

        UserDto(firstName="Kingsley", phoneNumber="080...")
        -> UserDto(first_name="Kingsley", phone_number="080...")

        model_dump(by_alias=True)
        -> {
            "firstName": "Kingsley",
            "phoneNumber": "080..."
        }
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )


class Object(CamelModel, AutoRepr):
    """
    Project-wide base DTO.

    Combines:

    - CamelModel:
        Automatic snake_case ↔ camelCase mapping
        for request/response payloads.

    - AutoRepr:
        Useful object representation for debugging/logging.

    All application DTOs should inherit from this class.
    """
    pass


# class CustomDateTime(TypeDecorator):
#     impl = DateTime
#
#     def process_bind_param(self, value, dialect):
#         return str_to_datetime(value)


class Base(DeclarativeBase):
    pass


class BaseEntity(Base, AutoRepr):
    __abstract__ = True

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()

    # __table_args__ = {
    #     'extend_existing': True,
    #     'postgresql_partition_by': 'RANGE (date_created)'  # Optional for large tables
    # }

    # UUID as PK (PostgreSQL-native)
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        index=True
    )

    # Optimized timestamp columns
    date_created = Column(
        TIMESTAMP(timezone=True),
        default=Utils.datetime_now_to_db,
        nullable=False,
        # index=True
    )

    created_by = Column(
        String(36),
        nullable=True
    )

    date_updated = Column(
        TIMESTAMP(timezone=True),
        nullable=True
    )

    updated_by = Column(
        String(36),
        nullable=True
    )

    # Soft delete pattern
    deleted = Column(
        Boolean,
        default=False,
        nullable=False,
        index=True  # Important for filtering active records
    )

    date_deleted = Column(
        TIMESTAMP(timezone=True),
        nullable=True
    )

    deleted_by = Column(
        String(36),
        nullable=True
    )

    version = Column(
        Integer,
        default=0,
        nullable=False
    )

    # __mapper_args__ = {
    #     'version_id_col': version,
    #     'version_id_generator': False  # Let PostgreSQL handle increments
    # }

    @hybrid_property
    def is_active(self):
        return ~self.deleted


class BaseQueryDto(Object):
    id: Optional[str] = Field(None, description='Unique ID')
    date_updated: Optional[datetime] = Field(None, description='Date updated')
    updated_by: Optional[str] = Field(None, description='Who updated the record')
    deleted: Optional[bool] = Field(None, description='Whether deleted')
    date_deleted: Optional[datetime] = Field(None, description='Date deleted')
    deleted_by: Optional[str] = Field(None, description='Who deleted the record')
    date_created: Optional[datetime] = Field(None, description='Date created')
    created_by: Optional[str] = Field(None, description='Who created thee record')
    version: Optional[int] = Field(None, description='The current version number of the record')


T = TypeVar('T', bound=Union[BaseQueryDto, bool, str, Object])


class SuccessResponse(Object, Generic[T]):
    """
    Single response
    """
    status: str = "success"
    code: str = "200"
    message: Optional[str] = None
    trace_id: Optional[str] = None

    data: Optional[T] = None


class PaginationMeta(Object):
    page: int = 0
    page_size: int = 10
    count: int = 0
    total: int = 0
    prev_page: Optional[int] = None
    next_page: Optional[int] = None


class Page(Object, Generic[T]):
    """
    Paginated response
    """
    status: str = "success"
    code: str = "200"
    message: Optional[str] = None
    trace_id: Optional[str] = None

    items: List[T]
    meta: PaginationMeta


# @dataclass  # use instead of Object for pydantic data validation
class PageRequest(Object):
    page: int = 0
    page_size: int = 10
    query_fields: Optional[str] = Field(None, description='Comma separated list of return fields')
    exact_string_values: Optional[bool] = True
    order_by: Optional[str] = Field('date_created desc', description='e.g: username asc, firstname desc')
    where: Optional[str] = Field(None, description='e.g: date_created >=')


ModelType = TypeVar("ModelType", bound=BaseEntity)
CreateSchemaType = TypeVar("CreateSchemaType", bound=Object)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=Object)
SearchSchemaType = TypeVar("SearchSchemaType", bound=BaseQueryDto)
QuerySchemaType = TypeVar("QuerySchemaType", bound=BaseQueryDto)
