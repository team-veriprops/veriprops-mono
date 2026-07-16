from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger
from kink import di
from starlette.requests import Request
from main.appodus_utils.db.redis_utils import RedisUtils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.integrations.models import IntegrationInitStore

logger: Logger = di["logger"]


@decorate_all_methods(method_trace_logger)
class IntegrationUtils:

    @staticmethod
    async def init_callback(ref_id: str, request: Request) -> None:
        frontend_origin = request.headers.get("referer")

        init_callback = IntegrationInitStore(
            frontend_origin=frontend_origin
        )
        # RedisUtils persists UTF-8 text only (no pickle) — store JSON and rehydrate
        # via IntegrationInitStore.model_validate_json on read, never the model object.
        await RedisUtils.set_redis(ref_id, init_callback.model_dump_json())
