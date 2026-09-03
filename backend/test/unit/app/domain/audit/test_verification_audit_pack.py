"""Unit tests for VerificationAuditPackService — S23 (R19.1, §19.3)."""
from __future__ import annotations

import csv
import io
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.audit.pack_service import VerificationAuditPackService
from main.appodus_utils.db.session import db_session_ctx


@pytest.fixture(autouse=True)
def mock_db_session():
    session = MagicMock()
    session.in_transaction.return_value = False

    @asynccontextmanager
    async def _begin():
        yield

    session.begin = _begin
    session.flush = AsyncMock()
    token = db_session_ctx.set(session)
    yield session
    db_session_ctx.reset(token)


def _transition():
    t = MagicMock()
    t.occurred_at = datetime(2026, 5, 1, tzinfo=timezone.utc)
    t.action = "VERIFICATION_STATE_CHANGED"
    t.actor_id = "admin-1"
    t.resource_type = "verification"
    t.resource_id = "vid-hex"
    t.from_state = "PAID"
    t.to_state = "IN_PROGRESS"
    t.ip_address = "1.2.3.4"
    t.details = {"note": "x"}
    return t


def _evidence():
    e = MagicMock()
    e.id = uuid.uuid4()
    e.kind = "PHOTO"
    e.content_sha256 = "deadbeef"
    e.task_id = "task-1"
    e.captured_at = datetime(2026, 5, 2, tzinfo=timezone.utc)
    return e


def _consent():
    c = MagicMock()
    c.accepted_at = datetime(2026, 4, 1, tzinfo=timezone.utc)
    c.document_type = "VERIFICATION_TERMS"
    c.consent_version = "1.0.0"
    c.ip_address = "9.9.9.9"
    c.device_fingerprint = "fp-1"
    return c


def _whatsapp_consent(utility_granted=True, marketing=False):
    """A §7.4.6 ledger row — the grant/revoke timestamp pairs, not a boolean."""
    c = MagicMock()
    c.utility_granted_at = datetime(2026, 8, 1, tzinfo=timezone.utc)
    c.utility_revoked_at = None if utility_granted else datetime(2026, 8, 5, tzinfo=timezone.utc)
    c.utility_source = "PAY_SCREEN"
    c.utility = utility_granted
    c.marketing_granted_at = datetime(2026, 8, 1, tzinfo=timezone.utc) if marketing else None
    c.marketing_revoked_at = None
    c.marketing_source = "PAY_SCREEN" if marketing else None
    c.marketing = marketing
    return c


def _make_svc(*, transitions, evidence, consents, whatsapp_consent=None):
    def _repo(list_result):
        r = MagicMock()
        r.list_for_verification = AsyncMock(return_value=list_result)
        return r

    verification = MagicMock()
    verification.id = uuid.uuid4()
    verification.customer_id = "cust-1"
    verification_repo = MagicMock()
    verification_repo.get_model = AsyncMock(return_value=verification)

    evidence_repo = MagicMock()
    evidence_repo.list_for_verification = AsyncMock(return_value=evidence)

    consent_repo = MagicMock()
    consent_repo.list_for_user = AsyncMock(return_value=(consents, len(consents)))

    whatsapp_consent_repo = MagicMock()
    whatsapp_consent_repo.get_by_user_id = AsyncMock(return_value=whatsapp_consent)

    audit = MagicMock()
    audit.list_pack_transitions = AsyncMock(return_value=transitions)

    return VerificationAuditPackService(
        verification_repo=verification_repo,
        task_repo=_repo([MagicMock(id=uuid.uuid4())]),
        payment_repo=_repo([MagicMock(id=uuid.uuid4())]),
        commission_repo=_repo([]),
        chargeback_repo=_repo([]),
        dispute_repo=_repo([]),
        recheck_repo=_repo([]),
        upgrade_repo=_repo([]),
        report_repo=_repo([]),
        share_repo=_repo([]),
        evidence_repo=evidence_repo,
        consent_repo=consent_repo,
        whatsapp_consent_repo=whatsapp_consent_repo,
        audit_service=audit,
    ), audit


class TestBuildPackCsv:
    async def test_pack_has_transition_evidence_and_consent_records(self):
        svc, audit = _make_svc(
            transitions=[_transition()], evidence=[_evidence()], consents=[_consent()],
        )
        data = await svc.build_pack_csv("vid-hex")

        rows = list(csv.reader(io.StringIO(data.decode("utf-8"))))
        header, body = rows[0], rows[1:]
        assert header[0] == "record_type"
        record_types = {r[0] for r in body}
        assert record_types == {"TRANSITION", "EVIDENCE", "CONSENT"}
        # evidence content hash carried through (§4.5 / §19.3)
        evidence_row = next(r for r in body if r[0] == "EVIDENCE")
        assert "deadbeef" in evidence_row[-1]

    async def test_transition_query_uses_full_resource_id_universe(self):
        svc, audit = _make_svc(transitions=[], evidence=[], consents=[])
        await svc.build_pack_csv("vid-hex")
        # vid + one task id + one payment id were gathered into the id set.
        resource_ids = audit.list_pack_transitions.call_args.args[0]
        assert len(resource_ids) == 3


class TestWhatsAppConsentExport:
    """§7.8 — "consent records timestamped and exportable".

    The §7.4.6 ledger was not in the pack before S11, so the one export a dispute or a
    regulator actually asks for could not show whether the customer had agreed to be
    messaged, or when they withdrew it.
    """

    async def test_a_live_opt_in_is_exported_with_its_timestamps_and_source(self):
        svc, _audit = _make_svc(
            transitions=[], evidence=[], consents=[],
            whatsapp_consent=_whatsapp_consent(utility_granted=True),
        )

        rows = list(csv.reader(io.StringIO((await svc.build_pack_csv("vid-hex")).decode())))
        consent_rows = [r for r in rows[1:] if r[0] == "WHATSAPP_CONSENT"]

        assert len(consent_rows) == 1
        assert consent_rows[0][2] == "GRANTED"
        assert "UTILITY" in consent_rows[0]
        # The pair is the record, so both halves and the capture point travel with it.
        assert "granted_at=2026-08-01" in consent_rows[0][-1]
        assert "source=PAY_SCREEN" in consent_rows[0][-1]

    async def test_a_withdrawn_consent_is_exported_as_withdrawn(self):
        # The state a complaint is actually about: they agreed, then they did not.
        svc, _audit = _make_svc(
            transitions=[], evidence=[], consents=[],
            whatsapp_consent=_whatsapp_consent(utility_granted=False),
        )

        rows = list(csv.reader(io.StringIO((await svc.build_pack_csv("vid-hex")).decode())))
        consent_rows = [r for r in rows[1:] if r[0] == "WHATSAPP_CONSENT"]

        assert consent_rows[0][2] == "REVOKED"
        assert "revoked_at=2026-08-05" in consent_rows[0][-1]

    async def test_a_customer_who_was_never_asked_produces_no_row(self):
        # Absence means both off (§7.4.6's unticked default). A row saying "declined"
        # would assert an event that never happened.
        svc, _audit = _make_svc(
            transitions=[], evidence=[], consents=[], whatsapp_consent=None,
        )

        rows = list(csv.reader(io.StringIO((await svc.build_pack_csv("vid-hex")).decode())))

        assert not [r for r in rows[1:] if r[0] == "WHATSAPP_CONSENT"]
