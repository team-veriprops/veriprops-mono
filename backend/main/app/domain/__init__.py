from fastapi import APIRouter

from main.app.config.settings import settings  # noqa: F401
from main.appodus_utils.config.bootstrap import BaseDiBootstrap  # noqa: F401
from main.app.domain.config.controller import config_router
# The WhatsApp channel: inbound arrives through the shared webhook router, and the
# handoff landings are public (the token is the authorization). The package import
# also keeps every channel model reachable for Alembic.
from main.app.domain import channel  # noqa: F401
from main.app.domain.channel.whatsapp.bot.intake_controller import whatsapp_intake_router
from main.app.domain.channel.whatsapp.bot.session.controller import whatsapp_bot_router
from main.app.domain.channel.whatsapp.handoff.controller import handoff_router
from main.app.domain.channel.whatsapp.link.controller import whatsapp_link_router
from main.app.domain.channel.whatsapp.template.controller import whatsapp_template_router
from main.app.domain.message.controller import message_router
from main.app.domain.user.controller import user_router
from main.app.domain.verification.controller import verification_router
from main.app.domain.verification.tracking.controller import customer_tracking_router
from main.app.domain.verification.report.controller import customer_report_router
from main.app.domain.verification.share.controller import share_router
from main.app.domain.verification.share.public_controller import public_share_router
from main.app.domain.verification.recheck.controller import recheck_router, admin_recheck_router
from main.app.domain.verification.upgrade.controller import upgrade_router
from main.app.domain.verification.dispute.controller import (
    dispute_router,
    agent_dispute_router,
    admin_dispute_router,
)
from main.app.domain.verification.admin.controller import admin_verification_router
from main.app.domain.verification.task.controller import agent_task_router
from main.app.domain.verification.scoring.controller import trust_weight_router
from main.app.domain.verification.pricing_config.controller import admin_pricing_router
from main.app.domain.verification.review.controller import review_router
from main.app.domain.communication.controller import (
    chat_router,
    verification_chat_router,
    admin_chat_router,
)
from main.app.domain.notification.controller import notification_router
from main.app.domain.notification_preference.controller import notification_preference_router
from main.app.domain.system_config.controller import system_config_router
from main.app.domain.commission_rule.controller import commission_rule_router
from main.app.domain.earnings.controller import earnings_router
from main.app.domain.payout.controller import payout_router, admin_payout_router
from main.app.domain.user.agent.reputation.controller import (
    agent_reputation_router,
    admin_suggested_agents_router,
)
from main.app.domain.referral.controller import referral_router
from main.app.domain.analytics.controller import analytics_router
from main.app.domain.broadcast.controller import broadcast_router
from main.app.domain.finance.controller import finance_router
from main.app.domain.payment.controller import payment_router

from main.appodus_utils.integrations.webhook import webhook_router
from main.app.domain.audit.controller import audit_router
from main.app.domain.compliance.erasure.controller import (
    erasure_router,
    admin_erasure_router,
)
from main.appodus_utils.config.settings import Environment

router = APIRouter()
router.include_router(config_router)
router.include_router(whatsapp_bot_router)
router.include_router(whatsapp_intake_router)
router.include_router(handoff_router)
router.include_router(whatsapp_link_router)
router.include_router(whatsapp_template_router)
router.include_router(message_router)
router.include_router(user_router)
router.include_router(verification_router)
router.include_router(customer_tracking_router)
router.include_router(customer_report_router)
router.include_router(share_router)
router.include_router(public_share_router)
router.include_router(recheck_router)
router.include_router(admin_recheck_router)
router.include_router(upgrade_router)
router.include_router(dispute_router)
router.include_router(agent_dispute_router)
router.include_router(admin_dispute_router)
router.include_router(admin_verification_router)
router.include_router(agent_task_router)
router.include_router(trust_weight_router)
router.include_router(admin_pricing_router)
router.include_router(review_router)
router.include_router(chat_router)
router.include_router(verification_chat_router)
router.include_router(admin_chat_router)
router.include_router(notification_router)
router.include_router(notification_preference_router)
router.include_router(system_config_router)
router.include_router(commission_rule_router)
router.include_router(earnings_router)
router.include_router(payout_router)
router.include_router(admin_payout_router)
router.include_router(agent_reputation_router)
router.include_router(admin_suggested_agents_router)
router.include_router(referral_router)
router.include_router(analytics_router)
router.include_router(broadcast_router)
router.include_router(finance_router)
router.include_router(payment_router)
router.include_router(audit_router)
router.include_router(erasure_router)
router.include_router(admin_erasure_router)
router.include_router(webhook_router)

# Dev/QA reset+seed — first production gate: the router only mounts in non-prod. The
# handlers also call `_require_non_prod()` (404 in prod) as the second gate.
if settings.ENVIRONMENT != Environment.PRODUCTION:
    from main.app.domain.dev.controller import dev_router
    router.include_router(dev_router)
