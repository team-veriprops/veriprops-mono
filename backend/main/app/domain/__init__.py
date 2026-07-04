from fastapi import APIRouter

from main.app.config.settings import settings  # noqa: F401
from main.appodus_utils.config.bootstrap import BaseDiBootstrap  # noqa: F401
from main.app.domain.config.controller import config_router
from main.app.domain.message.controller import message_router
from main.app.domain.user.controller import user_router
from main.app.domain.verification.controller import verification_router
from main.app.domain.verification.admin.controller import admin_verification_router
from main.app.domain.verification.task.controller import agent_task_router
from main.app.domain.verification.scoring.controller import trust_weight_router
from main.app.domain.verification.review.controller import review_router
from main.app.domain.payment.controller import payment_router

from main.appodus_utils.integrations.webhook import webhook_router
from main.app.domain.audit.controller import audit_router

router = APIRouter()
router.include_router(config_router)
router.include_router(message_router)
router.include_router(user_router)
router.include_router(verification_router)
router.include_router(admin_verification_router)
router.include_router(agent_task_router)
router.include_router(trust_weight_router)
router.include_router(review_router)
router.include_router(payment_router)
router.include_router(audit_router)
router.include_router(webhook_router)
