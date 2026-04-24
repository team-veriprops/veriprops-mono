from httpx import AsyncClient
from kink import di

from .common.commons import Utils, RouterUtils, FileUtils, Base64Utils
from .db.models import (
    AutoRepr, Object, BaseEntity, ModelType, CreateSchemaType, UpdateSchemaType,
    SearchSchemaType, QuerySchemaType, BaseQueryDto, Page, PageRequest
)



__all__ = [
    "Utils", "RouterUtils", "Base64Utils", "FileUtils",
    "AutoRepr",
    "Object",
    "BaseEntity",
    "ModelType",
    "CreateSchemaType",
    "UpdateSchemaType",
    "SearchSchemaType",
    "QuerySchemaType",
    "BaseQueryDto",
    "Page",
    "PageRequest"
]

# Provision some global Dependencies
di[AsyncClient] = lambda _di: AsyncClient(timeout=30.0)
