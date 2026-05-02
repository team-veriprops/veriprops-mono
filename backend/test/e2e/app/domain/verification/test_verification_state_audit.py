"""E2E integration test — verify that VerificationService.transition() writes an AuditLog row.

Pattern:
  * Module-level helper functions decorated with @transactional(ALWAYS_NEW) own their own
    sessions. Each helper commits atomically, making its writes visible to subsequent helpers.
  * The test class does NOT use @decorate_all_methods(transactional) so each step can run
    in an independent transaction, which lets us observe audit rows written by a prior step.
"""
import unittest

from kink import di

from main.app.domain.audit.models import AuditActionType, AuditLog, CreateAuditLogDto, SearchAuditLogDto
from main.app.domain.audit.repo import AuditLogRepo
from main.app.domain.audit.service import AuditLogService
from main.app.domain.verification.models import (
    CreateVerificationDto,
    Verification,
    VerificationStatus,
    VerificationTier,
)
from main.app.domain.verification.repo import VerificationRepo
from main.app.domain.verification.service import VerificationService
from main.appodus_utils import Utils
from main.appodus_utils.decorators.transactional import TransactionSessionPolicy, transactional
from test.utils.test_utils import truncate_entities

# ── DI-resolved singletons (module-level; DI bootstrapped by conftest.py) ─────

_verification_repo: VerificationRepo = di[VerificationRepo]
_verification_service: VerificationService = di[VerificationService]
_audit_repo: AuditLogRepo = di[AuditLogRepo]
_audit_service: AuditLogService = di[AuditLogService]


# ── ALWAYS_NEW helpers — each owns its own session and commits independently ──


@transactional(session_policy=TransactionSessionPolicy.ALWAYS_NEW)
async def _create_verification(vid: str, customer_id: str, status: VerificationStatus) -> str:
    """Insert a verification row and return its UUID string."""
    obj = await _verification_repo.create_return_model(
        CreateVerificationDto(
            vid=vid,
            customer_id=customer_id,
            tier=VerificationTier.STANDARD,
            status=status,
            draft_step=0,
        )
    )
    return str(obj.id)


@transactional(session_policy=TransactionSessionPolicy.ALWAYS_NEW)
async def _do_transition(verification_id: str, target: VerificationStatus, actor_id: str) -> None:
    """Call VerificationService.transition() in an isolated transaction.

    Because VerificationService uses USE_IF_PRESENT, it joins the ALWAYS_NEW session
    set by this helper. The helper's execute() is the outermost owner, so
    drain_audit_writes() fires here — committing the audit row atomically.
    """
    await _verification_service.transition(verification_id, target, actor_id=actor_id)


@transactional(session_policy=TransactionSessionPolicy.ALWAYS_NEW)
async def _direct_audit_create(
    action: AuditActionType,
    resource_type: str,
    resource_id: str,
    actor_id: str,
    from_state: str,
    to_state: str,
) -> None:
    """Insert an AuditLog row directly via the repo (bypasses schedule/drain)."""
    await _audit_repo.create(
        CreateAuditLogDto(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            actor_id=actor_id,
            from_state=from_state,
            to_state=to_state,
            occurred_at=Utils.datetime_now(),
        )
    )


@transactional(session_policy=TransactionSessionPolicy.ALWAYS_NEW)
async def _get_audit_rows(resource_id: str):
    """Return items list from a get_page filtered by resource_id."""
    page = await _audit_repo.get_page(
        SearchAuditLogDto(resource_id=resource_id, page=0, page_size=20)
    )
    return list(page.items)


# ── Test class ────────────────────────────────────────────────────────────────


class TestVerificationStateAudit(unittest.IsolatedAsyncioTestCase):

    async def asyncTearDown(self):
        await truncate_entities([AuditLog, Verification])

    # ── AuditLogRepo persistence ──────────────────────────────────────────────

    async def test_audit_log_repo_persists_and_retrieves_row(self):
        resource_id = "vid-repo-test-001"
        await _direct_audit_create(
            action=AuditActionType.VERIFICATION_SUBMITTED,
            resource_type="Verification",
            resource_id=resource_id,
            actor_id="user-test-001",
            from_state="DRAFT",
            to_state="SUBMITTED",
        )

        rows = await _get_audit_rows(resource_id)

        self.assertEqual(1, len(rows))
        row = rows[0]
        self.assertEqual(AuditActionType.VERIFICATION_SUBMITTED.value, row.action)
        self.assertEqual("Verification", row.resource_type)
        self.assertEqual(resource_id, row.resource_id)
        self.assertEqual("user-test-001", row.actor_id)
        self.assertEqual("DRAFT", row.from_state)
        self.assertEqual("SUBMITTED", row.to_state)

    # ── transition() writes audit row via schedule/drain ─────────────────────

    async def test_transition_writes_one_audit_log_row(self):
        vid = "VP-2026-TSTT01"
        customer_id = "cust-test-001"
        actor_id = "system"

        verification_id = await _create_verification(
            vid=vid,
            customer_id=customer_id,
            status=VerificationStatus.SUBMITTED,
        )

        # SUBMITTED → PAYMENT_PENDING is a valid transition per the state machine.
        await _do_transition(
            verification_id=verification_id,
            target=VerificationStatus.PAYMENT_PENDING,
            actor_id=actor_id,
        )

        rows = await _get_audit_rows(verification_id)

        self.assertEqual(1, len(rows))
        row = rows[0]
        self.assertEqual(AuditActionType.VERIFICATION_STATE_CHANGED.value, row.action)
        self.assertEqual("Verification", row.resource_type)
        self.assertEqual(verification_id, row.resource_id)
        self.assertEqual(actor_id, row.actor_id)
        self.assertEqual(VerificationStatus.SUBMITTED.value, row.from_state)
        self.assertEqual(VerificationStatus.PAYMENT_PENDING.value, row.to_state)

    async def test_multiple_transitions_write_multiple_rows(self):
        vid = "VP-2026-TSTT02"
        customer_id = "cust-test-002"

        verification_id = await _create_verification(
            vid=vid,
            customer_id=customer_id,
            status=VerificationStatus.SUBMITTED,
        )

        await _do_transition(verification_id, VerificationStatus.PAYMENT_PENDING, actor_id="sys")
        await _do_transition(verification_id, VerificationStatus.PAID, actor_id="payment-svc")
        await _do_transition(verification_id, VerificationStatus.IN_PROGRESS, actor_id="admin-1")

        rows = await _get_audit_rows(verification_id)

        self.assertEqual(3, len(rows))
        actions = [r.action for r in rows]
        self.assertEqual(
            actions,
            [AuditActionType.VERIFICATION_STATE_CHANGED.value] * 3,
        )
        to_states = [r.to_state for r in rows]
        self.assertIn(VerificationStatus.PAYMENT_PENDING.value, to_states)
        self.assertIn(VerificationStatus.PAID.value, to_states)
        self.assertIn(VerificationStatus.IN_PROGRESS.value, to_states)
