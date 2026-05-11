"""Unit tests for PDFGeneratorService (S36)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from main.app.domain.verification.report.pdf import PDFGeneratorService
from main.app.domain.verification.report.models import (
    CreateReportVersionDto,
    ReportVersion,
    UpdateReportVersionDto,
)
from main.app.domain.verification.report.assembly import ReportAssemblyService
from main.app.domain.verification.report.repo import ReportVersionRepo
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import ValidationException

_FAKE_PDF = b"%PDF-1.4 fake-pdf-content"


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


def _make_version(version_string: str = "v1.0", is_superseded: bool = False) -> MagicMock:
    v = MagicMock(spec=ReportVersion)
    v.id = "ver-1"
    v.vid = "VID-001"
    v.version_string = version_string
    v.is_superseded = is_superseded
    return v


def _make_report():
    from main.app.domain.verification.report.models import ReportDto
    return ReportDto(
        vid="VID-001",
        version="v1.0",
        tier="BASIC",
        completed_at=datetime(2026, 5, 11, tzinfo=timezone.utc),
        trust_score=Decimal("78.50"),
        executive_summary="Ownership chain verified.",
        registry_findings={"title_doc_assessment": "AUTHENTIC"},
        has_acknowledged=True,
    )


def _make_service(existing_version=None):
    assembly_svc = MagicMock(spec=ReportAssemblyService)
    assembly_svc.assemble = AsyncMock(return_value=_make_report())
    assembly_svc.build_template_context = MagicMock(return_value={
        "vid": "VID-001",
        "version": "v1.0",
        "tier": "BASIC",
        "completed_at": datetime(2026, 5, 11, tzinfo=timezone.utc),
        "trust_score": 78.5,
        "executive_summary": "Ownership chain verified.",
        "registry_findings": {"title_doc_assessment": "AUTHENTIC"},
        "physical_findings": None,
        "boundary_findings": None,
        "legal_opinion": None,
        "risk_summary": None,
        "is_standard_plus": False,
        "is_premium": False,
    })

    version_repo = MagicMock(spec=ReportVersionRepo)
    version_repo.current_for_vid = AsyncMock(return_value=existing_version)
    version_repo.create_return_model = AsyncMock(return_value=_make_version())
    version_repo.update = AsyncMock(return_value=_make_version(is_superseded=True))

    svc = PDFGeneratorService(assembly_svc=assembly_svc, version_repo=version_repo)
    return svc, assembly_svc, version_repo


class TestGetOrCreateVersion:
    async def test_creates_v1_when_no_existing_version(self):
        svc, _, version_repo = _make_service(existing_version=None)
        version = await svc.get_or_create_version("VID-001", "cust-1")
        version_repo.create_return_model.assert_called_once()
        call_arg: CreateReportVersionDto = version_repo.create_return_model.call_args[0][0]
        assert call_arg.version_string == "v1.0"
        assert call_arg.vid == "VID-001"

    async def test_returns_existing_version_without_creating(self):
        existing = _make_version("v1.0")
        svc, _, version_repo = _make_service(existing_version=existing)
        version = await svc.get_or_create_version("VID-001", "cust-1")
        version_repo.create_return_model.assert_not_called()
        assert version.version_string == "v1.0"

    async def test_second_generate_uses_cached_version(self):
        existing = _make_version("v1.0")
        svc, _, version_repo = _make_service(existing_version=existing)
        with patch.object(PDFGeneratorService, "_render_pdf", return_value=_FAKE_PDF):
            await svc.generate("VID-001", "cust-1")
        version_repo.create_return_model.assert_not_called()


class TestCreateNewVersion:
    async def test_bumps_to_v1_1_for_minor_fix(self):
        existing = _make_version("v1.0")
        svc, _, version_repo = _make_service(existing_version=existing)
        await svc.create_new_version("VID-001", reason="Minor correction to registry data", created_by="admin-1")
        call_arg: CreateReportVersionDto = version_repo.create_return_model.call_args[0][0]
        assert call_arg.version_string == "v1.1"

    async def test_bumps_to_v2_0_for_recheck(self):
        existing = _make_version("v1.0")
        svc, _, version_repo = _make_service(existing_version=existing)
        await svc.create_new_version("VID-001", reason="Re-check requested after dispute", created_by="admin-1")
        call_arg: CreateReportVersionDto = version_repo.create_return_model.call_args[0][0]
        assert call_arg.version_string == "v2.0"

    async def test_bumps_to_major_for_tier_upgrade(self):
        existing = _make_version("v1.0")
        svc, _, version_repo = _make_service(existing_version=existing)
        await svc.create_new_version("VID-001", reason="Tier upgrade from BASIC to STANDARD", created_by="admin-1")
        call_arg: CreateReportVersionDto = version_repo.create_return_model.call_args[0][0]
        assert call_arg.version_string == "v2.0"

    async def test_supersedes_current_version_before_creating_new(self):
        existing = _make_version("v1.0")
        svc, _, version_repo = _make_service(existing_version=existing)
        await svc.create_new_version("VID-001", reason="Minor correction to registry data")
        version_repo.update.assert_called_once_with("ver-1", UpdateReportVersionDto(is_superseded=True))

    async def test_raises_on_short_reason(self):
        svc, _, _ = _make_service(existing_version=_make_version("v1.0"))
        with pytest.raises(ValidationException):
            await svc.create_new_version("VID-001", reason="too short")


class TestWatermarkSuperseded:
    async def test_sets_is_superseded_true(self):
        svc, _, version_repo = _make_service()
        await svc.watermark_superseded("ver-1")
        version_repo.update.assert_called_once_with("ver-1", UpdateReportVersionDto(is_superseded=True))


class TestGenerate:
    async def test_returns_bytes_starting_with_pdf_header(self):
        existing = _make_version("v1.0")
        svc, _, _ = _make_service(existing_version=existing)
        with patch.object(PDFGeneratorService, "_render_pdf", return_value=_FAKE_PDF):
            result = await svc.generate("VID-001", "cust-1")
        assert isinstance(result, bytes)
        assert result.startswith(b"%PDF")

    async def test_generate_calls_assembly_service(self):
        existing = _make_version("v1.0")
        svc, assembly_svc, _ = _make_service(existing_version=existing)
        with patch.object(PDFGeneratorService, "_render_pdf", return_value=_FAKE_PDF):
            await svc.generate("VID-001", "cust-1")
        assembly_svc.assemble.assert_called_once_with("VID-001", "cust-1")

    async def test_generate_result_is_non_empty(self):
        existing = _make_version("v1.0")
        svc, _, _ = _make_service(existing_version=existing)
        with patch.object(PDFGeneratorService, "_render_pdf", return_value=_FAKE_PDF):
            result = await svc.generate("VID-001", "cust-1")
        assert len(result) > 0


class TestBumpVersion:
    def test_minor_fix_increments_minor(self):
        result = PDFGeneratorService._bump_version("v1.0", "Fixed a typo in the findings section")
        assert result == "v1.1"

    def test_recheck_increments_major(self):
        result = PDFGeneratorService._bump_version("v1.1", "re-check after new evidence submitted")
        assert result == "v2.0"

    def test_tier_upgrade_increments_major(self):
        result = PDFGeneratorService._bump_version("v2.0", "tier upgrade to PREMIUM")
        assert result == "v3.0"

    def test_re_verification_increments_major(self):
        result = PDFGeneratorService._bump_version("v1.0", "re-verification requested")
        assert result == "v2.0"

    def test_invalid_version_returns_v1_0(self):
        result = PDFGeneratorService._bump_version("invalid", "any reason here")
        assert result == "v1.0"
