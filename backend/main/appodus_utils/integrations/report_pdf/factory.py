"""Report PDF provider selection (§10.1).

Deterministic stub vs. real fpdf2 renderer, chosen by ``settings.REPORT_PDF_STUB_MODE`` —
same stub-first switch shape as the payment/storage/kyc facades.
"""
from __future__ import annotations

from kink import di, inject

from main.app.config.settings import settings
from main.appodus_utils.integrations.report_pdf.fpdf2.fpdf2_provider import Fpdf2ReportPdfProvider
from main.appodus_utils.integrations.report_pdf.interface import IReportPdfProvider
from main.appodus_utils.integrations.report_pdf.stub.stub_provider import StubReportPdfProvider


@inject
class ReportPdfProviderFactory:
    def get_active_provider(self) -> IReportPdfProvider:
        if settings.REPORT_PDF_STUB_MODE:
            return di[StubReportPdfProvider]
        return di[Fpdf2ReportPdfProvider]
