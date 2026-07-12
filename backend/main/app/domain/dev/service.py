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
    AgentRole,
    TaskState,
    VerificationStatus,
    VerificationTier,
)
from main.app.core.vid import generate_vid
from main.app.domain.audit.models import AuditActionType, AuditLog
from main.app.domain.payment.models import Payment, PaymentMethodKind, PaymentPurpose, PaymentStatus
from main.app.domain.property.models import Property
from main.app.domain.user.agent.coverage.models import AgentCoverage
from main.app.domain.user.agent.credential.models import (
    ROLE_REQUIRED_CREDENTIAL,
    AgentCredential,
    CredentialStatus,
)
from main.app.domain.user.agent.profile.models import AgentProfile
from main.app.domain.user.auth.session.models import UserType
from main.app.domain.user.models import User
from main.app.domain.verification.models import Verification
from main.app.domain.verification.task.models import ReviewDecision, VerificationTask
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
_REVIEW_APPROVED = ReviewDecision.APPROVED.value

# Domain tables cleared by reset() (order-independent — no FKs). Reference tables
# (consent_documents, trust_score_weight_config, key_values, users) are preserved.
_RESET_TABLES = [
    "chat_messages", "conversation_participants", "conversations",
    "notifications", "notification_preferences",
    "task_evidence", "verification_tasks", "reports", "report_acknowledgements",
    "commissions", "chargebacks", "admin_notes", "payments", "verifications", "properties",
    "agent_application_drafts", "agent_coverage", "agent_credentials", "kyc_records",
    "agent_profiles",
    # Post-completion lifecycle (§13/§14) + earnings (§15) — per-run scenario data.
    "verification_shares", "disputes", "recheck_requests", "upgrade_requests",
    "payouts", "agent_bank_accounts",
    # Growth (§17) + broadcasts (§18) — domain data, cleared for a clean scenario. Pricing
    # config + commission rules + system config are reference-like and preserved (seeded at start).
    "referral_credits", "referrals", "broadcasts",
    # Compliance (§19) — erasure requests are per-run scenario data.
    "data_erasure_requests",
    # Admin onboarding (§4) + messaging bookkeeping (rows accrue when ENABLE_OUT_MESSAGING=True).
    "admin_invitations", "messages",
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
        # Agents exist for every PREMIUM role (adds LAWYER beyond the STANDARD task set) so
        # the tier-upgrade leg can assign a credentialed lawyer without extra setup.
        agent_roles = roles_for_tier(VerificationTier.PREMIUM)
        agents = {}
        for i, role in enumerate(agent_roles):
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
            # Credentialed roles (§3.3a) need a VERIFIED, unexpired licence on file —
            # without it the role is inactive and the agent never ranks in suggestions.
            required_credential = ROLE_REQUIRED_CREDENTIAL.get(role)
            if required_credential is not None:
                session.add(self._new(
                    AgentCredential,
                    user_id=str(agent.id), role=role.value,
                    credential_type=required_credential.value,
                    licence_number=f"QA-{role.value}-0001",
                    expiry_date=Utils.datetime_now_plus(days=365).date(),
                    status=CredentialStatus.VERIFIED.value,
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

        # A second "ops" verification (IN_PROGRESS, SLA in the future) whose tasks are crafted
        # for the destructive/pool exercises — no-show reclaim, pool-starvation escalation,
        # decline→pool→re-accept, pause/delay, and the terminal fail+refund — so the primary
        # scenario verification (SLA sweep, analytics) is never disturbed.
        ops_prop = self._new(
            Property,
            customer_id=str(customer.id), property_type="LAND",
            address="Km 22 Lekki-Epe Expressway, Abijo", landmark="By the fuel station",
            state="Lagos", lga="Ibeju-Lekki",
        )
        session.add(ops_prop)
        ops = self._new(
            Verification,
            vid=generate_vid(), customer_id=str(customer.id),
            property_id=Utils.uuid_to_hex(ops_prop.id),
            tier=tier.value, status=VerificationStatus.IN_PROGRESS.value,
            price_locked_minor=15_000_000, currency=TransactionCurrency.NGN.value,
            paid_at=now, sla_due_date=Utils.datetime_now_plus(days=5).date(),
        )
        session.add(ops)
        ops_tx_ref = f"{ops.vid}-OPS"
        session.add(self._new(
            Payment,
            verification_id=Utils.uuid_to_hex(ops.id), customer_id=str(customer.id),
            purpose=PaymentPurpose.INITIAL.value, tx_ref=ops_tx_ref,
            method=PaymentMethodKind.CARD.value, status=PaymentStatus.SUCCEEDED.value,
            amount_minor=15_000_000, currency=TransactionCurrency.NGN.value,
        ))
        ops_hex = Utils.uuid_to_hex(ops.id)
        past, future = Utils.datetime_now_minus(hours=1), Utils.datetime_now_plus(hours=12)
        ops_task_specs = {
            # No-show fodder: manually assigned, accept deadline already blown.
            AgentRole.REGISTRY: dict(
                state=TaskState.ASSIGNED.value, assigned_agent_id=str(agents[AgentRole.REGISTRY].id),
                assignment_mode="MANUAL", assigned_at=now, accept_deadline_at=past,
            ),
            # Starvation fodder: sitting unclaimed in the pool past its window.
            AgentRole.FIELD: dict(
                state=TaskState.PENDING.value, in_pool=True,
                assignment_mode="BROADCAST", pool_expires_at=past,
            ),
            # Decline fodder: healthy manual assignment the agent will decline live.
            AgentRole.SURVEYOR: dict(
                state=TaskState.ASSIGNED.value, assigned_agent_id=str(agents[AgentRole.SURVEYOR].id),
                assignment_mode="MANUAL", assigned_at=now, accept_deadline_at=future,
            ),
        }
        ops_task_ids = {}
        for role, spec in ops_task_specs.items():
            task = self._new(
                VerificationTask,
                verification_id=ops_hex, role=role.value, tier=tier.value, **spec,
            )
            session.add(task)
            ops_task_ids[role.value] = str(task.id)

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
            "agents": {r.value: str(agents[r].id) for r in agent_roles},
            "verification": {"id": Utils.uuid_to_hex(verification.id), "vid": verification.vid,
                             "status": verification.status},
            "tasks": task_ids,
            "ops": {"id": ops_hex, "vid": ops.vid, "txRef": ops_tx_ref, "tasks": ops_task_ids},
        }

    async def latest_message(self, recipient: str) -> Dict[str, Any]:
        """Snapshot of the newest outbound-message row addressed to *recipient* (fragment
        match on the ``to`` JSON). Lets the e2e drive-through assert bookkeeping state
        (stored / sent / retrying / failed) without direct DB access. Returns
        ``{"found": False}`` instead of raising so callers can detect
        ``ENABLE_OUT_MESSAGING=False`` (no row ever created) and warn-skip."""
        session = get_db_session_from_context()
        row = (await session.execute(
            text(
                'SELECT id, status, retry_count, '
                'next_retry_at IS NOT NULL AS next_retry_at_set, '
                'expires_at IS NOT NULL AS expires_at_set, error '
                'FROM messages WHERE "to"::text ILIKE :frag '
                'ORDER BY date_created DESC LIMIT 1'
            ),
            {"frag": f"%{recipient}%"},
        )).first()
        if not row:
            return {"found": False}
        return {
            "found": True,
            "id": row.id.hex,
            "status": row.status,
            "retry_count": row.retry_count,
            "next_retry_at_set": row.next_retry_at_set,
            "expires_at_set": row.expires_at_set,
            "error": row.error,
        }

    async def rewind_message(self, recipient: str, rewind_expiry: bool = False) -> Dict[str, Any]:
        """Pull the newest matching message row's ``next_retry_at`` (and, when
        *rewind_expiry*, its ``expires_at``) into the past so the retry sweep fires
        immediately — the drive-through's determinism helper for the default
        ``[60, 300, 900]`` backoff ladder. Touches ONLY the timestamp columns: status
        and retry_count stay owned by the pipeline under test."""
        session = get_db_session_from_context()
        set_clause = "next_retry_at = now() - interval '1 second'"
        if rewind_expiry:
            set_clause += ", expires_at = now() - interval '1 second'"
        row = (await session.execute(
            text(
                f"UPDATE messages SET {set_clause} WHERE id = ("
                'SELECT id FROM messages WHERE "to"::text ILIKE :frag '
                "ORDER BY date_created DESC LIMIT 1) RETURNING id"
            ),
            {"frag": f"%{recipient}%"},
        )).first()
        return {"rewound": row is not None, "id": row.id.hex if row else None}

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
