"""PDF generation service — S36.

Renders the report as a PDF via WeasyPrint + Jinja2.
Handles version tracking: first call creates v1.0, subsequent calls return
the cached PDF key; superseded versions are flagged.
"""
from __future__ import annotations

import base64
import io
import os
from datetime import datetime, timezone
from typing import Optional

from kink import inject

from main.app.domain.verification.report.assembly import ReportAssemblyService
from main.app.domain.verification.report.models import (
    CreateReportVersionDto,
    ReportVersion,
    UpdateReportVersionDto,
)
from main.app.domain.verification.report.repo import ReportVersionRepo
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import ValidationException

_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class PDFGeneratorService:
    def __init__(
        self,
        assembly_svc: ReportAssemblyService,
        version_repo: ReportVersionRepo,
    ):
        self._assembly = assembly_svc
        self._versions = version_repo

    async def generate(self, vid: str, customer_id: str) -> bytes:
        """Return PDF bytes for the report. Uses cached version if available."""
        report = await self._assembly.assemble(vid, customer_id)
        version = await self.get_or_create_version(vid, customer_id)

        ctx = self._assembly.build_template_context(report)
        ctx["qr_data_uri"] = self._build_qr_data_uri(vid)
        ctx["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        ctx["version"] = version.version_string

        return self._render_pdf(ctx)

    async def get_or_create_version(self, vid: str, customer_id: Optional[str] = None) -> ReportVersion:
        existing = await self._versions.current_for_vid(vid)
        if existing:
            return existing
        now = datetime.now(timezone.utc)
        return await self._versions.create_return_model(
            CreateReportVersionDto(
                vid=vid,
                version_string="v1.0",
                pdf_s3_key=None,
                created_at=now,
                created_by=customer_id,
            )
        )

    async def create_new_version(self, vid: str, reason: str, created_by: Optional[str] = None) -> ReportVersion:
        if not reason or len(reason.strip()) < 10:
            raise ValidationException(message="Version bump reason must be at least 10 characters")

        current = await self._versions.current_for_vid(vid)
        new_version_string = self._bump_version(current.version_string if current else "v0.0", reason)

        if current:
            await self.watermark_superseded(str(current.id))

        now = datetime.now(timezone.utc)
        return await self._versions.create_return_model(
            CreateReportVersionDto(
                vid=vid,
                version_string=new_version_string,
                pdf_s3_key=None,
                created_at=now,
                created_by=created_by,
            )
        )

    async def watermark_superseded(self, version_id: str) -> None:
        await self._versions.update(version_id, UpdateReportVersionDto(is_superseded=True))

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _bump_version(current: str, reason: str) -> str:
        """
        Bumping rules (from plan D decision):
        - re-check  → major (v1.0 → v2.0)
        - tier upgrade → major
        - minor fix → minor (v1.0 → v1.1)
        """
        try:
            core = current.lstrip("v")
            major, minor = core.split(".")
            major, minor = int(major), int(minor)
        except (ValueError, AttributeError):
            return "v1.0"

        lower = reason.lower()
        if any(kw in lower for kw in ("re-check", "recheck", "tier upgrade", "re-verification")):
            return f"v{major + 1}.0"
        return f"v{major}.{minor + 1}"

    @staticmethod
    def _build_qr_data_uri(vid: str) -> str:
        try:
            import qrcode
            from qrcode.image.pure import PyPNGImage

            qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=4, border=2)
            qr.add_data(f"https://veriprops.com/verify/{vid}")
            qr.make(fit=True)
            img = qr.make_image(image_factory=PyPNGImage)
            buf = io.BytesIO()
            img.save(buf)
            encoded = base64.b64encode(buf.getvalue()).decode()
            return f"data:image/png;base64,{encoded}"
        except Exception:
            return ""

    @staticmethod
    def _render_pdf(context: dict) -> bytes:
        try:
            from jinja2 import Environment, FileSystemLoader, select_autoescape
            from weasyprint import HTML

            env = Environment(
                loader=FileSystemLoader(_TEMPLATE_DIR),
                autoescape=select_autoescape(["html"]),
            )
            template = env.get_template("report.html.jinja2")
            html_content = template.render(**context)
            pdf_bytes = HTML(string=html_content).write_pdf()
            return pdf_bytes
        except Exception as exc:
            raise ValidationException(message=f"PDF generation failed: {exc}") from exc
