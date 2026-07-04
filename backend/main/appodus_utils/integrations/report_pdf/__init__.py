"""Report PDF facade (PRD §10.1).

Provider-agnostic server-side PDF generation for the final report, selected by
``settings.REPORT_PDF_STUB_MODE`` like the payment/storage/kyc facades. The default
``fpdf2`` provider is pure-Python (no native deps — Windows/CI-safe, D16); the stub is
a deterministic minimal renderer for fast tests. Both carry the legal footer on every
page (§10.2 parity exit criterion).

Takes a primitive :class:`ReportPdfContext` (not an app DTO) so this integration stays
decoupled from the domain layer, consistent with the other integrations.
"""
from main.appodus_utils.integrations.report_pdf.factory import ReportPdfProviderFactory
from main.appodus_utils.integrations.report_pdf.interface import IReportPdfProvider
from main.appodus_utils.integrations.report_pdf.models import ReportPdfContext, ReportPdfSection

__all__ = [
    "IReportPdfProvider",
    "ReportPdfProviderFactory",
    "ReportPdfContext",
    "ReportPdfSection",
]
