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

from main.app.config.settings import settings
from main.app.domain.audit.service import AuditLogService
from main.app.domain.commission.repo import CommissionRepo
from main.app.domain.payment.chargeback.repo import ChargebackRepo
from main.app.domain.payment.repo import PaymentRepo
from main.app.domain.channel.whatsapp.consent.models import WhatsAppConsentKind
from main.app.domain.channel.whatsapp.consent.repo import WhatsAppConsentRepo
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
_CONSENT_PAGE = settings.AUDIT_PACK_CONSENT_PAGE_SIZE

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
        whatsapp_consent_repo: WhatsAppConsentRepo,
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
        self._whatsapp_consents = whatsapp_consent_repo
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
        whatsapp_consent = await self._whatsapp_consents.get_by_user_id(
            str(verification.customer_id)
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

        # §7.4.6 messaging consent, one row per opt-in (§7.8: "consent records timestamped
        # and exportable"). Emitted from the grant/revoke timestamp pair rather than from
        # the derived boolean, because the pair *is* the record — a pack that said only
        # "marketing: false" could not show when it was given, when it was withdrawn, or
        # which surface the customer used to do either.
        for row in _whatsapp_consent_rows(whatsapp_consent):
            writer.writerow(row)

        return buf.getvalue().encode("utf-8")


def _whatsapp_consent_rows(consent) -> List[list]:
    """The §7.4.6 opt-ins as pack rows — one per consent, or none if never asked.

    Absence of a row means both consents are off (§7.4.6 requires unticked defaults), and
    that is represented by emitting nothing rather than by two rows saying "false": a pack
    that asserts a customer declined is making a claim about an event that never happened.
    """
    if consent is None:
        return []

    rows: List[list] = []
    for kind, granted_at, revoked_at, source, granted in (
        (WhatsAppConsentKind.UTILITY, consent.utility_granted_at,
         consent.utility_revoked_at, consent.utility_source, consent.utility),
        (WhatsAppConsentKind.MARKETING, consent.marketing_granted_at,
         consent.marketing_revoked_at, consent.marketing_source, consent.marketing),
    ):
        if granted_at is None and revoked_at is None:
            continue
        # `occurred_at` is the most recent decision, so the pack sorts by when the
        # customer last acted rather than by when they first did.
        occurred = max(filter(None, (granted_at, revoked_at)))
        rows.append([
            "WHATSAPP_CONSENT",
            occurred.isoformat(),
            "GRANTED" if granted else "REVOKED",
            "", "whatsapp_consent", kind.value, "", "", "",
            f"granted_at={granted_at.isoformat() if granted_at else ''}; "
            f"revoked_at={revoked_at.isoformat() if revoked_at else ''}; "
            f"source={source or ''}",
        ])
    return rows
