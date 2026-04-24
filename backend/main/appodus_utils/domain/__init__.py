from fastapi import APIRouter



from main.appodus_utils.common.utils_settings import utils_settings
from main.appodus_utils.config.bootstrap import BaseDiBootstrap

from main.appodus_utils import RouterUtils
from main.appodus_utils.domain.key_value.models import KeyValue

utils_router = APIRouter(prefix="/v1", tags=["Utils"])

RouterUtils.add_routers(utils_router, [])