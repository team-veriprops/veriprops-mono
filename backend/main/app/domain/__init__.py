from fastapi import APIRouter

from main.app.config.settings import settings  # noqa: F401
from main.appodus_utils.config.bootstrap import BaseDiBootstrap  # noqa: F401
from main.appodus_utils.config.settings import Environment
from main.app.domain.audit import models as _audit_models  # noqa: F401
from main.app.domain.admin_config import models as _admin_config_models  # noqa: F401
from main.app.domain.admin_config.controller import admin_config_router
from main.app.domain.user.controller import user_router
from main.app.domain.verification import models as _verification_models  # noqa: F401
from main.app.domain.verification.controller import verification_router
from main.app.domain.verification.admin.controller import admin_verification_router
from main.app.domain.verification.task import models as _task_models  # noqa: F401
from main.app.domain.verification.task.controller import admin_task_router, agent_task_router
from main.app.domain.verification.task.review.controller import task_review_router
from main.app.domain.verification.conflict.controller import conflict_router
from main.app.domain.verification.scoring.controller import scoring_router
from main.app.domain.verification.release.controller import release_router
from main.app.domain.verification.portal.controller import portal_router, public_router
from main.app.domain.verification.portal.dashboard_controller import portal_dashboard_router
from main.app.domain.verification.portal.stream import stream_router
from main.app.domain.payment import models as _payment_models  # noqa: F401
from main.app.domain.payment.controller import payment_router
from main.app.domain.thread import (  # noqa: F401
    MessageThread as _ThreadModel,
    ThreadMessage as _ThreadMessageModel,
    FraudFlag as _FraudFlagModel,
)
from main.app.domain.thread import thread_router, ws_router, fraud_router
from main.app.domain.notification import (  # noqa: F401
    Notification as _NotificationModel,
    NotificationDispatch as _NotificationDispatchModel,
    NotificationPreference as _NotificationPrefModel,
)
from main.app.domain.notification import notification_router
from main.app.domain.verification.share import (  # noqa: F401
    ShareLink as _ShareLinkModel,
    ShareRecipient as _ShareRecipientModel,
)
from main.app.domain.verification.share import share_router
from main.app.domain.verification.recheck import RecheckRequest as _RecheckModel  # noqa: F401
from main.app.domain.verification.recheck import recheck_router
from main.app.domain.verification.tier_upgrade import TierUpgrade as _TierUpgradeModel  # noqa: F401
from main.app.domain.verification.tier_upgrade import tier_upgrade_router
from main.app.domain.verification.dispute import (  # noqa: F401
    Dispute as _DisputeModel,
    DisputeResolution as _DisputeResolutionModel,
)
from main.app.domain.verification.dispute import dispute_router
from main.app.domain.commission import (  # noqa: F401
    CommissionRule as _CommissionRuleModel,
    Earning as _EarningModel,
)
from main.app.domain.commission import commission_router
from main.app.domain.payout import (  # noqa: F401
    BankAccount as _BankAccountModel,
    Payout as _PayoutModel,
    PayoutAdjustment as _PayoutAdjustmentModel,
)
from main.app.domain.payout import payout_router
from main.app.domain.referral import (  # noqa: F401
    ReferralCode as _ReferralCodeModel,
    ReferralRedemption as _ReferralRedemptionModel,
)
from main.app.domain.referral import referral_router
from main.app.domain.user.agent.models import AgentQualityScore as _AgentQualityScoreModel  # noqa: F401
from main.app.domain.verification.pricing import models as _pricing_models  # noqa: F401
from main.app.domain.verification.pricing.controller import pricing_admin_router
from main.app.domain.content import models as _content_models  # noqa: F401
from main.app.domain.content.controller import content_admin_router, public_content_router
from main.app.domain.broadcast import models as _broadcast_models  # noqa: F401
from main.app.domain.broadcast.controller import broadcast_router
from main.appodus_utils.integrations.webhook import webhook_router
from main.app.domain.analytics.controller import analytics_router
from main.app.domain.audit.controller import audit_router
from main.app.domain.retention import models as _retention_models  # noqa: F401
from main.app.domain.retention.controller import retention_router

router = APIRouter()
router.include_router(admin_config_router)
router.include_router(admin_verification_router)
router.include_router(admin_task_router)
router.include_router(task_review_router)
router.include_router(conflict_router)
router.include_router(scoring_router)
router.include_router(release_router)
router.include_router(portal_router)
router.include_router(portal_dashboard_router)
router.include_router(public_router)
router.include_router(stream_router)
router.include_router(agent_task_router)
router.include_router(user_router)
router.include_router(verification_router)
router.include_router(payment_router)
router.include_router(thread_router)
router.include_router(fraud_router)
router.include_router(ws_router)
router.include_router(notification_router)
router.include_router(share_router)
router.include_router(recheck_router)
router.include_router(tier_upgrade_router)
router.include_router(dispute_router)
router.include_router(commission_router)
router.include_router(payout_router)
router.include_router(referral_router)
router.include_router(analytics_router)
router.include_router(audit_router)
router.include_router(retention_router)
router.include_router(pricing_admin_router)
router.include_router(content_admin_router)
router.include_router(public_content_router)
router.include_router(broadcast_router)
router.include_router(webhook_router)

# Dev/test-only endpoints — never mounted in production
if settings.ENVIRONMENT != Environment.PRODUCTION:
    from main.app.domain.dev.controller import dev_router
    router.include_router(dev_router)
