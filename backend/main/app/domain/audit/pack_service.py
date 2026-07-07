"""Verification audit-pack builder — §19.3 (R19.1).

Assembles the *legally defensible export pack* for a single verification: the
verification record plus every transition across its whole object graph (tasks,
payments/refunds, disputes, re-checks, tier upgrades, reports, shares,
commissions, chargebacks, evidence), the evidence content hashes (§4.5), and the
owning customer's versioned consent snapshots — as one flat CSV.

Admin-only; wired at GET /admin/audit/verifications/{vid}/export. This service
holds no entity of its own — it is an orchestration layer that reads across
domains (each related repo exposes ``list_for_verification``) and delegates the
transition query + row shaping to AuditLogService.
"""
from __future__ import annotations

import csv
import io
import json
from typing import List

from kink import inject

from main.app.domain.audit.service import AuditLogService
from main.app.domain.commission.repo import CommissionRepo
from main.app.domain.payment.chargeback.repo import ChargebackRepo
from main.app.domain.payment.repo import PaymentRepo
from main.app.domain.user.auth.consent.repo import UserConsentRepo
from main.app.domain.verification.dispute.repo import DisputeRepo
from main.app.domain.verification.recheck.repo import RecheckRepo
from main.app.domain.verification.report.repo import ReportRepo
from main.app.domain.verification.repo import VerificationRepo
from main.app.domain.verification.share.repo import VerificationShareRepo
from main.app.domain.verification.task.evidence.repo import EvidenceRepo
from main.app.domain.verification.task.repo import VerificationTaskRepo
from main.app.domain.verification.upgrade.repo import UpgradeRepo
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import ResourceNotFoundException

# Upper bound on consent snapshots pulled into a single pack (a user accrues few).
_CONSENT_PAGE = 1000

_PACK_COLUMNS = [
    "record_type", "occurred_at", "action", "actor_id",
    "resource_type", "resource_id", "from_state", "to_state", "ip_address", "detail",
]


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class VerificationAuditPackService:
    def __init__(
        self,
        verification_repo: VerificationRepo,
        task_repo: VerificationTaskRepo,
        payment_repo: PaymentRepo,
        commission_repo: CommissionRepo,
        chargeback_repo: ChargebackRepo,
        dispute_repo: DisputeRepo,
        recheck_repo: RecheckRepo,
        upgrade_repo: UpgradeRepo,
        report_repo: ReportRepo,
        share_repo: VerificationShareRepo,
        evidence_repo: EvidenceRepo,
        consent_repo: UserConsentRepo,
        audit_service: AuditLogService,
    ):
        self._verifications = verification_repo
        self._tasks = task_repo
        self._payments = payment_repo
        self._commissions = commission_repo
        self._chargebacks = chargeback_repo
        self._disputes = dispute_repo
        self._rechecks = recheck_repo
        self._upgrades = upgrade_repo
        self._reports = report_repo
        self._shares = share_repo
        self._evidence = evidence_repo
        self._consents = consent_repo
        self._audit = audit_service

    async def build_pack_csv(self, verification_id: str) -> bytes:
        """Return the §19.3 audit pack for a verification as CSV bytes."""
        verification = await self._verifications.get_model(verification_id)
        if not verification:
            raise ResourceNotFoundException(resource="verification")
        vid_hex = Utils.uuid_to_hex(verification.id)

        tasks = await self._tasks.list_for_verification(verification_id)
        evidence = await self._evidence.list_for_verification(verification_id)

        # Every audited resource in the verification's object graph. Resource ids are
        # globally unique UUIDs, so a single id-set query captures all transitions.
        resource_ids: List[str] = [vid_hex]
        for group in (
            tasks,
            await self._payments.list_for_verification(verification_id),
            await self._commissions.list_for_verification(verification_id),
            await self._chargebacks.list_for_verification(verification_id),
            await self._disputes.list_for_verification(verification_id),
            await self._rechecks.list_for_verification(verification_id),
            await self._upgrades.list_for_verification(verification_id),
            await self._reports.list_for_verification(verification_id),
            await self._shares.list_for_verification(verification_id),
            evidence,
        ):
            resource_ids.extend(Utils.uuid_to_hex(row.id) for row in group)

        transitions = await self._audit.list_pack_transitions(resource_ids)
        consents, _ = await self._consents.list_for_user(
            str(verification.customer_id), offset=0, limit=_CONSENT_PAGE
        )

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(_PACK_COLUMNS)

        # Transition backbone (verification + every child resource).
        for t in transitions:
            writer.writerow([
                "TRANSITION",
                t.occurred_at.isoformat() if t.occurred_at else "",
                t.action, t.actor_id or "", t.resource_type, t.resource_id,
                t.from_state or "", t.to_state or "", t.ip_address or "",
                json.dumps(t.details) if t.details else "",
            ])

        # Evidence content hashes (§4.5 tamper-evidence).
        for e in evidence:
            writer.writerow([
                "EVIDENCE",
                e.captured_at.isoformat() if e.captured_at else "",
                e.kind, "", "task_evidence", Utils.uuid_to_hex(e.id), "", "", "",
                f"sha256={e.content_sha256}; task={e.task_id}",
            ])

        # Versioned consent snapshots for the owning customer.
        for c in consents:
            writer.writerow([
                "CONSENT",
                c.accepted_at.isoformat() if c.accepted_at else "",
                c.document_type, "", "user_consent", c.consent_version, "", "",
                c.ip_address or "",
                f"version={c.consent_version}; fingerprint={c.device_fingerprint or ''}",
            ])

        return buf.getvalue().encode("utf-8")
