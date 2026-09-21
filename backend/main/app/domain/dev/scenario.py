"""Isolated verification-lifecycle scenarios for browser automation (non-production only).

`POST /dev/scenario` hands a browser spec a verification already standing at a lifecycle
stage, with its own customer and its own approved agents. Two properties make it worth
having beside `/dev/seed`:

- **The real services drive every transition.** Draft, submit, payment, assignment, task
  execution, review, release, dispute, re-check and commission clearance all run through the
  service methods the controllers and jobs call, so state, audit rows, commissions, reports and
  domain events are what production produces — a spec starting here tests the app, not a
  hand-built imitation of it. The one exception is a timestamp no service can advance without
  waiting days (a commission's clearance date), which is moved into the past before the real
  clearance sweep runs.
- **Every call is isolated.** Fresh people per scenario is what lets specs run in parallel:
  no other spec's tasks count against these agents' capacity cap (§6.5), and no other spec's
  notifications land in this customer's bell.

Each action commits in its own session (`ALWAYS_NEW`), exactly as the separate HTTP requests
of a real journey do. Chaining them inside one transaction would re-fetch rows created moments
earlier and not yet committed, where `get_model` can return `None`.
"""
from __future__ import annotations

import enum
import secrets
from typing import Awaitable, Callable, Dict, FrozenSet, List, Optional, Set, Tuple, TypeVar

from kink import inject
from sqlalchemy import text

from main.app.config.settings import settings
from main.app.core.state.dependencies import is_unlocked, roles_for_tier
from main.app.core.state.status import AgentRole, VerificationStatus, VerificationTier
from main.app.domain.commission.models import CommissionStatus
from main.app.domain.dev.fixtures import (
    QA_PASSWORD,
    add_approved_agent,
    add_verified_user,
    record_required_consents,
    unique_local_phone,
    unique_qa_email,
)
from main.app.domain.earnings.service import EarningsService
from main.app.domain.payment.models import PaymentMethodKind, PaymentWebhookDto
from main.app.domain.payment.service import PaymentService
from main.app.domain.payout.bank_account.models import AddBankAccountDto
from main.app.domain.payout.bank_account.service import BankAccountService
from main.app.domain.property.models import PropertyInputDto, PropertyType
from main.app.domain.system_config.models import ConfigKey
from main.app.domain.system_config.service import ConfigService
from main.app.domain.user.auth.consent.models import ConsentDocumentType
from main.app.domain.user.auth.session.models import UserPersona
from main.app.domain.user.service import UserService
from main.app.domain.verification.dispute.models import DisputeType, OpenDisputeDto
from main.app.domain.verification.dispute.service import DisputeService
from main.app.domain.verification.models import SubmitVerificationDto, VerificationConsentDto
from main.app.domain.verification.recheck.models import RequestRecheckDto
from main.app.domain.verification.recheck.service import RecheckService
from main.app.domain.verification.review.service import ReviewService
from main.app.domain.verification.service import VerificationService
from main.app.domain.verification.task.evidence.models import EvidenceKind
from main.app.domain.verification.task.service import VerificationTaskService
from main.appodus_utils import Object, Utils
from main.appodus_utils.db.session import get_db_session_from_context
from main.appodus_utils.db.types.money import TransactionCurrency
from main.appodus_utils.decorators.transactional import TransactionSessionPolicy, transactional
from main.appodus_utils.exception.exceptions import ValidationException

T = TypeVar("T")


class ScenarioStage(str, enum.Enum):
    """Where a scenario leaves its verification.

    The stages up to RELEASED are cumulative: each includes every earlier one. The last three are
    alternative branches off a released case — each includes RELEASED, but never another branch.
    """

    DRAFT = "DRAFT"                        # an empty draft owned by the customer
    SUBMITTED = "SUBMITTED"                # property + tier + consent submitted, price locked
    PAID = "PAID"                          # stub payment confirmed
    ASSIGNED = "ASSIGNED"                  # every unlocked role assigned to its scenario agent
    IN_PROGRESS = "IN_PROGRESS"            # those agents accepted, started and uploaded evidence
    UNDER_REVIEW = "UNDER_REVIEW"          # every task submitted (dependency waves included)
    REVIEW_APPROVED = "REVIEW_APPROVED"    # every task review-approved — ready to release
    RELEASED = "RELEASED"                  # released → COMPLETED with its first report
    DISPUTED = "DISPUTED"                  # branch: the customer disputed the released report
    RECHECK_REQUESTED = "RECHECK_REQUESTED"  # branch: a re-check is pending the admin's decision
    PAYOUT_READY = "PAYOUT_READY"          # branch: commissions cleared, agents can withdraw


POST_RELEASE_BRANCHES: FrozenSet[ScenarioStage] = frozenset({
    ScenarioStage.DISPUTED, ScenarioStage.RECHECK_REQUESTED, ScenarioStage.PAYOUT_READY,
})
_LINEAR_ORDER: List[ScenarioStage] = [s for s in ScenarioStage if s not in POST_RELEASE_BRANCHES]

# Minimal valid role forms — the required fields `task/validator.py` enforces (§12.2).
ROLE_SUBMISSIONS: Dict[AgentRole, dict] = {
    AgentRole.REGISTRY: {"registered_owner": "Chief A. Danladi", "title_search_result": "CLEAN",
                         "search_reference": "LAG/REG/2026/0042", "summary": "Registry search clear."},
    AgentRole.FIELD: {"occupancy_status": "VACANT", "physical_condition": "Fenced, cleared plot.",
                      "summary": "Site visit uneventful."},
    AgentRole.SURVEYOR: {"area_sqm": 648, "beacon_status": "ALL_PRESENT",
                         "summary": "Beacons match the survey plan."},
    AgentRole.LAWYER: {"legal_opinion": "Title chain is coherent.", "risk_level": "LOW",
                       "recommendation": "PROCEED", "summary": "No encumbrances found."},
}

# 1×1 transparent PNG — the smallest valid proof-of-work a task will accept (§12.3).
EVIDENCE_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d4944415478da63fcffffff7f000705fe02fea72d874e0000000049454e44ae426082"
)
REVIEW_QUALITY = 90
RELEASE_REASON = "Scenario release — all checks passed."
DISPUTE_DESCRIPTION = (
    "The boundary survey in this report does not match the beacons on site: the eastern boundary "
    "sits several metres inside the line drawn on the registered survey plan."
)
RECHECK_REASON = "The seller has produced a newer survey plan; please re-check the boundaries."


class BuildScenarioDto(Object):
    stage: ScenarioStage
    tier: VerificationTier = VerificationTier.STANDARD
    # False leaves the customer at their first payment with an unverified phone, so a spec
    # can drive the pay-step phone gate (§10.5). Only meaningful before PAID — a stage that
    # pays needs the gate already cleared.
    customer_phone_verified: bool = True


class ScenarioAccountDto(Object):
    """A login-able participant; every scenario account shares the QA password."""

    id: str
    email: str
    password: str


class ScenarioAgentDto(ScenarioAccountDto):
    task_id: Optional[str] = None
    # PAYOUT_READY only: the agent's withdrawable balance and the stored beneficiary to pay into.
    available_minor: Optional[int] = None
    bank_account_id: Optional[str] = None


class ScenarioDto(Object):
    stage: ScenarioStage
    verification_id: str
    vid: str
    status: VerificationStatus
    tier: VerificationTier
    customer: ScenarioAccountDto
    agents: Dict[AgentRole, ScenarioAgentDto]
    dispute_id: Optional[str] = None   # DISPUTED only
    recheck_id: Optional[str] = None   # RECHECK_REQUESTED only


def stage_reached(target: ScenarioStage, stage: ScenarioStage) -> bool:
    """True when a scenario built to *target* passes through *stage*."""
    if stage in POST_RELEASE_BRANCHES:
        return target == stage
    effective = ScenarioStage.RELEASED if target in POST_RELEASE_BRANCHES else target
    return _LINEAR_ORDER.index(effective) >= _LINEAR_ORDER.index(stage)


def padded_to(text_: str, min_chars: int) -> str:
    """*text_* repeated until it is at least *min_chars* long (a configured minimum can grow)."""
    padded = text_
    while len(padded) < min_chars:
        padded = f"{padded} {text_}"
    return padded


@inject
class DevScenarioService:
    def __init__(
        self,
        verification_service: VerificationService,
        payment_service: PaymentService,
        verification_task_service: VerificationTaskService,
        review_service: ReviewService,
        user_service: UserService,
        dispute_service: DisputeService,
        recheck_service: RecheckService,
        earnings_service: EarningsService,
        bank_account_service: BankAccountService,
        config_service: ConfigService,
    ):
        self._verification_service = verification_service
        self._payment_service = payment_service
        self._verification_task_service = verification_task_service
        self._review_service = review_service
        self._user_service = user_service
        self._dispute_service = dispute_service
        self._recheck_service = recheck_service
        self._earnings_service = earnings_service
        self._bank_account_service = bank_account_service
        self._config_service = config_service

    async def build(self, req: BuildScenarioDto) -> ScenarioDto:
        target, tier = req.stage, req.tier
        if not req.customer_phone_verified and stage_reached(target, ScenarioStage.PAID):
            raise ValidationException(
                message="A scenario that pays needs a customer whose phone is verified.",
            )
        customer, agents = await self._create_people(
            tier, customer_phone_verified=req.customer_phone_verified,
        )
        agent_ids = {role: agent.id for role, agent in agents.items()}

        draft = await self._step(lambda: self._verification_service.create_draft(customer.id))
        verification_id, vid = Utils.uuid_to_hex(draft.id), draft.vid
        task_ids: Dict[AgentRole, str] = {}
        dispute_id: Optional[str] = None
        recheck_id: Optional[str] = None
        payout_accounts: Dict[AgentRole, Tuple[int, str]] = {}

        if stage_reached(target, ScenarioStage.SUBMITTED):
            await self._submit(verification_id, customer.id, tier)
        if stage_reached(target, ScenarioStage.PAID):
            await self._pay(verification_id, customer.id)
        if stage_reached(target, ScenarioStage.ASSIGNED):
            admin_id = await self._super_admin_id()
            await self._execute_tasks(target, tier, verification_id, admin_id, agent_ids, task_ids)
            if stage_reached(target, ScenarioStage.REVIEW_APPROVED):
                for role in roles_for_tier(tier):
                    await self._step(lambda role=role: self._review_service.approve_task(
                        verification_id, role, REVIEW_QUALITY, admin_id,
                    ))
            if stage_reached(target, ScenarioStage.RELEASED):
                await self._step(lambda: self._review_service.release(
                    verification_id, admin_id, RELEASE_REASON,
                ))

        if target == ScenarioStage.DISPUTED:
            dispute_id = await self._open_dispute(verification_id, customer.id)
        elif target == ScenarioStage.RECHECK_REQUESTED:
            recheck = await self._step(lambda: self._recheck_service.request(
                verification_id, customer.id, RequestRecheckDto(reason=RECHECK_REASON),
            ))
            recheck_id = Utils.uuid_to_hex(recheck.id)
        elif target == ScenarioStage.PAYOUT_READY:
            payout_accounts = await self._make_payout_ready(verification_id, agent_ids)

        final = await self._step(
            lambda: self._verification_service.get_owned(verification_id, customer.id)
        )
        return ScenarioDto(
            stage=target, verification_id=verification_id, vid=vid,
            status=VerificationStatus(final.status), tier=tier, customer=customer,
            agents={
                role: ScenarioAgentDto(
                    id=agent.id, email=agent.email, password=agent.password,
                    task_id=task_ids.get(role),
                    available_minor=payout_accounts[role][0] if role in payout_accounts else None,
                    bank_account_id=payout_accounts[role][1] if role in payout_accounts else None,
                )
                for role, agent in agents.items()
            },
            dispute_id=dispute_id, recheck_id=recheck_id,
        )

    async def _execute_tasks(
        self, target: ScenarioStage, tier: VerificationTier, verification_id: str,
        admin_id: str, agent_ids: Dict[AgentRole, str], task_ids: Dict[AgentRole, str],
    ) -> None:
        """Drive the tier's tasks in dependency waves (§12.1).

        A role locked behind upstream submissions (LAWYER on PREMIUM) cannot even be assigned
        until those siblings have SUBMITTED, so each wave is the roles unlocked by the wave
        before it. A scenario stopping before UNDER_REVIEW therefore leaves locked roles
        unassigned — which is exactly the state a real case would be in.
        """
        roles = roles_for_tier(tier)
        submitted: Set[AgentRole] = set()
        while True:
            wave = [r for r in roles if r not in task_ids and is_unlocked(tier, r, submitted)]
            if not wave:
                return
            for role in wave:
                task = await self._step(lambda role=role: self._verification_task_service.assign(
                    verification_id, role, agent_ids[role], admin_id,
                ))
                task_ids[role] = Utils.uuid_to_hex(task.id)
            if not stage_reached(target, ScenarioStage.IN_PROGRESS):
                return
            for role in wave:
                await self._start_with_evidence(task_ids[role], agent_ids[role])
            if not stage_reached(target, ScenarioStage.UNDER_REVIEW):
                return
            for role in wave:
                await self._step(lambda role=role: self._verification_task_service.submit(
                    task_ids[role], agent_ids[role], ROLE_SUBMISSIONS[role],
                ))
                submitted.add(role)

    async def _start_with_evidence(self, task_id: str, agent_id: str) -> None:
        await self._step(lambda: self._verification_task_service.accept(task_id, agent_id))
        await self._step(lambda: self._verification_task_service.start(task_id, agent_id))
        await self._step(lambda: self._verification_task_service.add_evidence(
            task_id, agent_id, file_bytes=EVIDENCE_PNG, kind=EvidenceKind.PHOTO,
            mime_type="image/png", gps_latitude=6.4478, gps_longitude=3.4723,
        ))

    async def _submit(self, verification_id: str, customer_id: str, tier: VerificationTier) -> None:
        consent_version = await self._verification_terms_version()
        dto = SubmitVerificationDto(
            property=PropertyInputDto(
                property_type=PropertyType.LAND, address="12 Scenario Close, Lekki Phase 1",
                landmark="Beside the estate gate", state="Lagos", lga="Eti-Osa",
            ),
            tier=tier, currency=TransactionCurrency.NGN,
            consent=VerificationConsentDto(consent_version=consent_version),
        )
        await self._step(lambda: self._verification_service.submit(verification_id, customer_id, dto))

    async def _pay(self, verification_id: str, customer_id: str) -> None:
        """Initiate a card payment, then confirm it the way the stub gateway's webhook does."""
        payment = await self._step(lambda: self._payment_service.initiate(
            verification_id, customer_id, PaymentMethodKind.CARD,
        ))
        tx_ref = payment.tx_ref
        await self._step(lambda: self._payment_service.handle_webhook(
            PaymentWebhookDto(event_id=f"stub-{tx_ref}", tx_ref=tx_ref, succeeded=True)
        ))

    async def _open_dispute(self, verification_id: str, customer_id: str) -> str:
        """The customer disputes the released report (§14.3), with a description long enough
        for the configured minimum so the real validation accepts it."""
        min_chars = await self._step(
            lambda: self._config_service.get_int(ConfigKey.DISPUTE_MIN_DESCRIPTION_CHARS)
        )
        dto = OpenDisputeDto(
            dispute_type=DisputeType.INACCURATE_FINDING,
            description=padded_to(DISPUTE_DESCRIPTION, min_chars),
            target_role=AgentRole.SURVEYOR,
        )
        dispute = await self._step(lambda: self._dispute_service.open(verification_id, customer_id, dto))
        return Utils.uuid_to_hex(dispute.id)

    async def _make_payout_ready(
        self, verification_id: str, agent_ids: Dict[AgentRole, str],
    ) -> Dict[AgentRole, Tuple[int, str]]:
        """Clear the commissions release accrued, then give each agent a stored beneficiary.

        Clearance is days away by design (§15.2), so its date is moved into the past and the real
        clearance sweep does the CLEARING → AVAILABLE transition."""
        await self._backdate_commission_clearance(verification_id)
        await self._step(self._earnings_service.sweep_cleared)

        accounts: Dict[AgentRole, Tuple[int, str]] = {}
        for role, agent_id in agent_ids.items():
            bank_account = await self._step(lambda role=role, agent_id=agent_id: self._bank_account_service.add(
                agent_id, AddBankAccountDto(
                    bank_name="Scenario Bank", account_number=f"{secrets.randbelow(10 ** 10):010d}",
                    account_name=f"{role.value.title()} Agent", is_default=True,
                ),
            ))
            available = await self._step(lambda agent_id=agent_id: self._earnings_service.available_minor(agent_id))
            accounts[role] = (available, Utils.uuid_to_hex(bank_account.id))
        return accounts

    @transactional(session_policy=TransactionSessionPolicy.ALWAYS_NEW)
    async def _step(self, action: Callable[[], Awaitable[T]]) -> T:
        """Run one lifecycle action in its own committed session, as its own request would."""
        return await action()

    @transactional(session_policy=TransactionSessionPolicy.ALWAYS_NEW)
    async def _backdate_commission_clearance(self, verification_id: str) -> None:
        """Move this case's clearing commissions past their clearance date — the one timestamp
        a scenario cannot reach through a service without waiting days."""
        session = get_db_session_from_context()
        await session.execute(
            text(
                "UPDATE commissions SET clearing_until = now() - interval '1 second' "
                "WHERE verification_id = :verification_id AND status = :status"
            ),
            {"verification_id": verification_id, "status": CommissionStatus.CLEARING.value},
        )

    @transactional(session_policy=TransactionSessionPolicy.ALWAYS_NEW)
    async def _create_people(
        self, tier: VerificationTier, *, customer_phone_verified: bool = True,
    ) -> Tuple[ScenarioAccountDto, Dict[AgentRole, ScenarioAccountDto]]:
        """A fresh customer plus one approved agent per role the tier requires."""
        session = get_db_session_from_context()
        now = Utils.datetime_now()

        customer_email = unique_qa_email("qa-scn-customer")
        customer = add_verified_user(
            session, first_name="Ada", last_name="Scenario", email=customer_email,
            phone_local=unique_local_phone(), persona=UserPersona.CUSTOMER.value,
            phone_verified=customer_phone_verified,
        )
        agents: Dict[AgentRole, ScenarioAccountDto] = {}
        for role in roles_for_tier(tier):
            email = unique_qa_email(f"qa-scn-{role.value.lower()}")
            agent = add_approved_agent(
                session, role, email=email, phone_local=unique_local_phone(), now=now,
            )
            agents[role] = ScenarioAccountDto(id=str(agent.id), email=email, password=QA_PASSWORD)

        await record_required_consents(
            session, [str(customer.id)] + [a.id for a in agents.values()], now,
            include_super_admin=False,
        )
        await session.flush()
        return (
            ScenarioAccountDto(id=str(customer.id), email=customer_email, password=QA_PASSWORD),
            agents,
        )

    @transactional(session_policy=TransactionSessionPolicy.ALWAYS_NEW)
    async def _super_admin_id(self) -> str:
        """The admin every scenario review action is attributed to."""
        admin = await self._user_service.get_user_by_email(settings.SUPER_ADMIN_EMAIL)
        return str(admin.id)

    @transactional(session_policy=TransactionSessionPolicy.ALWAYS_NEW)
    async def _verification_terms_version(self) -> str:
        """The current verification-terms version — a superseded one is rejected at submit."""
        session = get_db_session_from_context()
        row = (await session.execute(
            text(
                "SELECT consent_version FROM consent_documents WHERE type = :type "
                "ORDER BY effective_at DESC LIMIT 1"
            ),
            {"type": ConsentDocumentType.VERIFICATION_TERMS.value},
        )).first()
        return row.consent_version
