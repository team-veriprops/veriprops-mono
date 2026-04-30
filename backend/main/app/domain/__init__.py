from fastapi import APIRouter

from main.app.config.settings import settings # noqa: F401
from main.appodus_utils.config.bootstrap import BaseDiBootstrap # noqa: F401
# Importing these modules registers their ORM models with SQLAlchemy's metadata
from main.app.domain.user.controller import user_router

router = APIRouter()
router.include_router(user_router)
