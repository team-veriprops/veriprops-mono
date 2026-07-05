"""ShareService (§13.1, §13.2): public VID lookup state routing + summary no-leak, tokenised
link/named shares, revocation + expiry invalidation, named-recipient disclaimer gate."""
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.core.state.status import ShareType, VerificationStatus, VerificationTier
from main.app.domain.property.models import PropertyType
from main.app.domain.verification.report.models import CustomerReportDto
from main.app.domain.verification.share.models import (
    CreateShareRequestDto,
    PublicLookupState,
)
from main.app.domain.verification.share.service import ShareService
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import ValidationException


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


def _now():
    return datetime.now(timezone.utc)


def _verification(status=VerificationStatus.COMPLETED, public=True):
    return SimpleNamespace(
        id="v-1", vid="VP-ABC123", tier=VerificationTier.STANDARD.value,
        property_id="p-1", status=status.value, public_lookup_enabled=public,
    )


def _report():
    return SimpleNamespace(
        id="rep-1", verification_id="v-1", report_version=2,
        composite_trust_score=88, released_at=_now(),
    )


def _property():
    return SimpleNamespace(
        property_type=PropertyType.LAND.value, state="Lagos", lga="Eti-Osa",
        address="12 Secret Lane, Lekki",
    )


def _share(share_type=ShareType.LINK_SUMMARY, *, revoked=False, expired=False, acked=False):
    return SimpleNamespace(
        id="s-1", verification_id="v-1", share_type=share_type.value,
        token="tok-123", recipient_email="friend@example.com",
        expires_at=_now() - timedelta(days=1) if expired else _now() + timedelta(days=10),
        revoked_at=_now() if revoked else None,
        first_viewed_at=None,
        disclaimer_acked_at=_now() if acked else None,
        date_created=_now(),
    )


def _service(*, verification=None, report=True, share=None, property_=None):
    svc = object.__new__(ShareService)
    svc._repo = MagicMock()
    svc._verification_repo = MagicMock()
    svc._verifications = MagicMock()
    svc._reports = MagicMock()
    svc._customer_report = MagicMock()
    svc._properties = MagicMock()
    svc._messages = MagicMock()
    svc._audit = MagicMock()

    v = verification if verification is not None else _verification()
    svc._verification_repo.get_by_vid = AsyncMock(return_value=v)
    svc._verification_repo.get_model = AsyncMock(return_value=v)
    svc._verifications.get_owned = AsyncMock(return_value=v)
    svc._reports.get_released = AsyncMock(return_value=_report() if report else None)
    svc._properties.get_model = AsyncMock(return_value=property_ or _property())
    svc._repo.get_by_token = AsyncMock(return_value=share)
    svc._repo.get_model = AsyncMock(return_value=share)
    svc._repo.create_return_model = AsyncMock(return_value=_share())
    svc._repo.list_for_verification = AsyncMock(return_value=[_share()])
    svc._customer_report.build_shared_content = AsyncMock(
        return_value=CustomerReportDto(
            id="rep-1", verification_id="v-1", vid="VP-ABC123", report_version=2, trust_score=88,
        )
    )
    svc._messages.send_report_share = AsyncMock()
    svc._audit.schedule = MagicMock()
    return svc


class TestPublicLookup:
    async def test_unknown_vid_is_not_found(self):
        svc = _service()
        svc._verification_repo.get_by_vid = AsyncMock(return_value=None)
        out = await svc.public_lookup("VP-NOPE")
        assert out.state == PublicLookupState.NOT_FOUND

    async def test_completed_public_returns_summary(self):
        svc = _service()
        out = await svc.public_lookup("VP-ABC123")
        assert out.state == PublicLookupState.SHARED
        assert out.verified is True
        assert out.trust_band == "Caution"  # 88 → Caution band, never the number
        assert out.tier == VerificationTier.STANDARD
        assert out.property_type == PropertyType.LAND
        assert out.state_region == "Lagos"
        assert out.lga == "Eti-Osa"
        assert out.report_version == 2

    async def test_summary_never_leaks_score_or_address(self):
        """§13.1 allow-list: the summary carries no numeric score and no full address."""
        svc = _service()
        out = await svc.public_lookup("VP-ABC123")
        payload = out.model_dump()
        assert "trust_score" not in payload
        assert "address" not in payload
        # The full street address must never appear anywhere in the summary payload.
        assert "Secret Lane" not in str(payload)
        assert isinstance(out.trust_band, str)

    async def test_completed_but_not_public_is_private(self):
        svc = _service(verification=_verification(public=False))
        out = await svc.public_lookup("VP-ABC123")
        assert out.state == PublicLookupState.PRIVATE

    async def test_in_progress_status(self):
        svc = _service(verification=_verification(status=VerificationStatus.IN_PROGRESS))
        out = await svc.public_lookup("VP-ABC123")
        assert out.state == PublicLookupState.IN_PROGRESS

    async def test_disputed_status(self):
        svc = _service(verification=_verification(status=VerificationStatus.DISPUTED))
        out = await svc.public_lookup("VP-ABC123")
        assert out.state == PublicLookupState.DISPUTED


class TestResolveShared:
    async def test_link_summary_returns_summary(self):
        svc = _service(share=_share(ShareType.LINK_SUMMARY))
        out = await svc.resolve_shared("tok-123")
        assert out.state == PublicLookupState.SHARED
        assert out.summary is not None
        assert out.report is None

    async def test_revoked_token_is_not_found(self):
        svc = _service(share=_share(revoked=True))
        out = await svc.resolve_shared("tok-123")
        assert out.state == PublicLookupState.NOT_FOUND

    async def test_expired_token_is_not_found(self):
        svc = _service(share=_share(expired=True))
        out = await svc.resolve_shared("tok-123")
        assert out.state == PublicLookupState.NOT_FOUND

    async def test_named_full_requires_acknowledgement_first(self):
        svc = _service(share=_share(ShareType.NAMED_FULL, acked=False))
        out = await svc.resolve_shared("tok-123")
        assert out.requires_acknowledgement is True
        assert out.report is None
        assert out.summary is not None

    async def test_named_full_acked_returns_full_report(self):
        svc = _service(share=_share(ShareType.NAMED_FULL, acked=True))
        out = await svc.resolve_shared("tok-123")
        assert out.requires_acknowledgement is False
        assert out.report is not None


class TestAcknowledgeShared:
    async def test_acknowledge_sets_ack_and_returns_report(self):
        share = _share(ShareType.NAMED_FULL, acked=False)
        svc = _service(share=share)
        # After ack the stored row reads acked → resolve returns the full report.
        svc._repo.get_model = AsyncMock(return_value=share)

        async def _ack(_id):
            share.disclaimer_acked_at = _now()

        svc._set_acked = _ack
        out = await svc.acknowledge_shared("tok-123")
        assert share.disclaimer_acked_at is not None
        assert out.report is not None


class TestCreateShare:
    async def test_named_share_requires_email(self):
        svc = _service()
        with pytest.raises(ValidationException):
            await svc.create_share(
                "v-1", "cust-1",
                CreateShareRequestDto(share_type=ShareType.NAMED_FULL, recipient_email=" "),
            )

    async def test_requires_released_report(self):
        svc = _service(report=False)
        with pytest.raises(ValidationException):
            await svc.create_share(
                "v-1", "cust-1", CreateShareRequestDto(share_type=ShareType.LINK_SUMMARY),
            )

    async def test_named_share_emails_the_recipient(self):
        svc = _service()
        svc._repo.create_return_model = AsyncMock(return_value=_share(ShareType.NAMED_FULL))
        await svc.create_share(
            "v-1", "cust-1",
            CreateShareRequestDto(share_type=ShareType.NAMED_FULL, recipient_email="a@b.com"),
        )
        svc._messages.send_report_share.assert_awaited_once()


class TestRevoke:
    async def test_revoke_sets_revoked_at(self):
        share = _share()          # verification_id="v-1", not yet revoked
        svc = _service(share=share)
        # get_owned returns a verification whose (string) id hashes to the share's stored id.
        svc._verifications.get_owned = AsyncMock(return_value=SimpleNamespace(id="v-1", vid="VP-ABC123"))

        async def _revoke(_id):
            share.revoked_at = _now()

        svc._set_revoked = _revoke
        out = await svc.revoke_share("v-1", "s-1", "cust-1")
        assert share.revoked_at is not None
        assert out.active is False
