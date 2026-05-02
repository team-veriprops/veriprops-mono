from fastapi import APIRouter

from main.app.config.settings import settings  # noqa: F401
from main.appodus_utils.config.bootstrap import BaseDiBootstrap  # noqa: F401
# Importing these modules registers their ORM models with SQLAlchemy's metadata
from main.app.domain.audit import models as _audit_models  # noqa: F401
from main.app.domain.user.controller import user_router
from main.app.domain.verification import models as _verification_models  # noqa: F401
from main.app.domain.verification.controller import verification_router
from main.app.domain.payment import models as _payment_models  # noqa: F401
from main.app.domain.payment.controller import payment_router

router = APIRouter()
router.include_router(user_router)
router.include_router(verification_router)
router.include_router(payment_router)
