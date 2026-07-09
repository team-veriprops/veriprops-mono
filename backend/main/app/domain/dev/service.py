"""Deterministic dev/QA seeding (non-production only).

``reset()`` clears domain data (keeping the super-admin + reference seeds); ``seed()`` builds a
coherent scenario for the e2e drive-through: a login-able customer, a few agents, and a
verification in ``UNDER_REVIEW`` (every required task SUBMITTED + review-approved, SLA overdue)
so an admin can immediately drive release, hold-review, and the SLA sweep against real data.
"""
from __future__ import annotations

from typing import Any, Dict

from kink import inject
from sqlalchemy import text

from main.app.config.settings import settings
from main.app.core.state.dependencies import roles_for_tier
from main.app.core.state.status import (
    TaskState,
    VerificationStatus,
    VerificationTier,
)
from main.app.core.vid import generate_vid
from main.app.domain.audit.models import AuditActionType, AuditLog
from main.app.domain.payment.models import Payment, PaymentMethodKind, PaymentPurpose, PaymentStatus
from main.app.domain.property.models import Property
from main.app.domain.user.agent.coverage.models import AgentCoverage
from main.app.domain.user.agent.profile.models import AgentProfile
from main.app.domain.user.auth.session.models import UserType
from main.app.domain.user.models import User
from main.app.domain.verification.models import Verification
from main.app.domain.verification.task.models import VerificationTask
from main.appodus_utils import Utils
from main.appodus_utils.db.session import get_db_session_from_context
from main.appodus_utils.db.types.money import TransactionCurrency
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.transactional import transactional

# Deterministic e2e credentials (non-prod only). A non-special-use domain — the email
# validator rejects reserved TLDs like `.test`/`example.com`.
CUSTOMER_EMAIL = "qa-customer@veriprops.io"
CUSTOMER_PASSWORD = "Test1234!"
AGENT_PASSWORD = "Test1234!"
# A disposable second customer used only by the §19 data-erasure e2e — erasing this
# account (login fail + tokenised PII) never disturbs the primary scenario checks.
ERASABLE_EMAIL = "qa-erasable@veriprops.io"
ERASABLE_PASSWORD = "Test1234!"
_REVIEW_APPROVED = "APPROVED"

# Domain tables cleared by reset() (order-independent — no FKs). Reference tables
# (consent_documents, trust_score_weight_config, key_values, users) are preserved.
_RESET_TABLES = [
    "chat_messages", "conversation_participants", "conversations",
    "notifications", "notification_preferences",
    "task_evidence", "verification_tasks", "reports", "report_acknowledgements",
    "commissions", "chargebacks", "admin_notes", "payments", "verifications", "properties",
    "agent_application_drafts", "agent_coverage", "agent_credentials", "kyc_records",
    "agent_profiles",
    # Growth (§17) + broadcasts (§18) — domain data, cleared for a clean scenario. Pricing
    # config + commission rules + system config are reference-like and preserved (seeded at start).
    "referral_credits", "referrals", "broadcasts",
    # Compliance (§19) — erasure requests are per-run scenario data.
    "data_erasure_requests",
]


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
class DevSeedService:
    async def reset(self) -> Dict[str, Any]:
        """Hard-clear domain data + non-super-admin users (non-prod QA reset)."""
        session = get_db_session_from_context()
        for table in _RESET_TABLES:
            await session.execute(text(f"DELETE FROM {table}"))
        await session.execute(
            text("DELETE FROM users WHERE email <> :admin"),
            {"admin": settings.SUPER_ADMIN_EMAIL},
        )
        return {"reset": True, "tables_cleared": len(_RESET_TABLES) + 1}

    async def seed(self) -> Dict[str, Any]:
        """Seed a customer + agents + an UNDER_REVIEW, SLA-overdue verification with
        review-approved tasks. Idempotent-ish: call reset() first for a clean scenario."""
        session = get_db_session_from_context()
        now = Utils.datetime_now()

        customer = self._new(
            User,
            first_name="Chidi", last_name="Okafor",
            email=CUSTOMER_EMAIL, email_normalized=CUSTOMER_EMAIL, email_verified=True,
            phone_country_code="NG", phone_dial_code="+234", phone="8030000001",
            phone_e164="+2348030000001", phone_verified=True,
            country_of_residence="NG", timezone="Africa/Lagos", preferred_currency="NGN",
            user_type=UserType.USER.value, personas=["CUSTOMER"], trust_status="TRUSTED",
            password_hash=Utils.get_password_hash(CUSTOMER_PASSWORD),
        )
        session.add(customer)

        tier = VerificationTier.STANDARD
        roles = roles_for_tier(tier)
        agents = {}
        for i, role in enumerate(roles):
            agent = self._new(
                User,
                first_name=role.value.title(), last_name="Agent",
                email=f"qa-agent-{role.value.lower()}@veriprops.io",
                email_normalized=f"qa-agent-{role.value.lower()}@veriprops.io", email_verified=True,
                phone_country_code="NG", phone_dial_code="+234", phone=f"803000010{i}",
                phone_e164=f"+234803000010{i}", phone_verified=True,
                country_of_residence="NG", timezone="Africa/Lagos", preferred_currency="NGN",
                user_type=UserType.USER.value, personas=["AGENT"], trust_status="TRUSTED",
                password_hash=Utils.get_password_hash(AGENT_PASSWORD),
            )
            session.add(agent)
            agents[role] = agent
            # An APPROVED agent profile + coverage (§16) so reputation/ranking has real data.
            session.add(self._new(
                AgentProfile,
                user_id=str(agent.id), roles=[role.value], approved_roles=[role.value],
                status="APPROVED", availability="GREEN", submitted_at=now, reviewed_at=now,
            ))
            session.add(self._new(
                AgentCoverage, user_id=str(agent.id), state="lagos", lga="eti-osa",
            ))

        prop = self._new(
            Property,
            customer_id=str(customer.id), property_type="LAND",
            address="Plot 15 Admiralty Way, Lekki Phase 1", landmark="Near the roundabout",
            state="Lagos", lga="Eti-Osa",
        )
        session.add(prop)

        verification = self._new(
            Verification,
            vid=generate_vid(), customer_id=str(customer.id),
            property_id=Utils.uuid_to_hex(prop.id),
            tier=tier.value, status=VerificationStatus.UNDER_REVIEW.value,
            price_locked_minor=15_000_000, currency=TransactionCurrency.NGN.value,
            paid_at=now, sla_due_date=Utils.datetime_now_minus(days=3).date(),
        )
        session.add(verification)

        # A SUCCEEDED payment so revenue analytics / finance / mission-control reflect real
        # collected money (§18.1) — the seed is paid, not just marked paid_at (D24 extension).
        session.add(self._new(
            Payment,
            verification_id=Utils.uuid_to_hex(verification.id), customer_id=str(customer.id),
            purpose=PaymentPurpose.INITIAL.value, tx_ref=f"{verification.vid}-SEED",
            method=PaymentMethodKind.CARD.value, status=PaymentStatus.SUCCEEDED.value,
            amount_minor=15_000_000, currency=TransactionCurrency.NGN.value,
        ))

        task_ids = {}
        for role in roles:
            task = self._new(
                VerificationTask,
                verification_id=Utils.uuid_to_hex(verification.id), role=role.value, tier=tier.value,
                state=TaskState.SUBMITTED.value, assigned_agent_id=str(agents[role].id),
                assignment_mode="MANUAL", submission_payload={"summary": "clear"},
                review_decision=_REVIEW_APPROVED, review_quality=95,
                assigned_at=now, accepted_at=now, submitted_at=now,
            )
            session.add(task)
            task_ids[role.value] = str(task.id)

        # A few audit transitions for the verification so the §19.3 export pack has a real
        # trail (the seed builds rows directly, bypassing the services that normally audit).
        vid_hex = Utils.uuid_to_hex(verification.id)
        for action, frm, to in (
            (AuditActionType.VERIFICATION_SUBMITTED, None, VerificationStatus.SUBMITTED.value),
            (AuditActionType.VERIFICATION_STATE_CHANGED,
             VerificationStatus.PAID.value, VerificationStatus.IN_PROGRESS.value),
        ):
            session.add(self._new(
                AuditLog, actor_id=str(customer.id), action=action.value,
                resource_type="verification", resource_id=vid_hex,
                from_state=frm, to_state=to, ip_address="203.0.113.5", occurred_at=now,
            ))

        # A disposable customer for the data-erasure e2e, plus audit rows it is the actor of
        # (so pseudonymisation of the audit actor identity is observable, §4.11).
        erasable = self._new(
            User,
            first_name="Ngozi", last_name="Eze",
            email=ERASABLE_EMAIL, email_normalized=ERASABLE_EMAIL, email_verified=True,
            phone_country_code="NG", phone_dial_code="+234", phone="8030009999",
            phone_e164="+2348030009999", phone_verified=True,
            country_of_residence="NG", timezone="Africa/Lagos", preferred_currency="NGN",
            user_type=UserType.USER.value, personas=["CUSTOMER"], trust_status="TRUSTED",
            password_hash=Utils.get_password_hash(ERASABLE_PASSWORD),
        )
        session.add(erasable)
        for action in (AuditActionType.CONSENT_RECORDED, AuditActionType.PAYMENT_INITIATED):
            session.add(self._new(
                AuditLog, actor_id=str(erasable.id), action=action.value,
                resource_type="user", resource_id=str(erasable.id),
                ip_address="198.51.100.7", occurred_at=now,
            ))

        await session.flush()
        return {
            "customer": {"id": str(customer.id), "email": CUSTOMER_EMAIL, "password": CUSTOMER_PASSWORD},
            "erasable": {"id": str(erasable.id), "email": ERASABLE_EMAIL, "password": ERASABLE_PASSWORD},
            "admin": {"email": settings.SUPER_ADMIN_EMAIL, "password": settings.SUPER_ADMIN_PASSWORD},
            "agents": {r.value: str(agents[r].id) for r in roles},
            "verification": {"id": Utils.uuid_to_hex(verification.id), "vid": verification.vid,
                             "status": verification.status},
            "tasks": task_ids,
        }

    @staticmethod
    def _new(model, **fields):
        """Construct a BaseEntity row with the audit bookkeeping the repos set on create.

        ``id`` is a real ``UUID`` (not a str) so SQLAlchemy's insertmanyvalues sentinel
        matching lines up with what asyncpg returns."""
        obj = model(**fields)
        obj.id = Utils.generate_uuid()
        obj.version = 1
        obj.deleted = False
        obj.date_created = Utils.datetime_now()
        return obj
