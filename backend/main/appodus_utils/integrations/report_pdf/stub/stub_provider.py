"""Deterministic minimal report PDF renderer for fast tests (§10.1).

Selected when ``REPORT_PDF_STUB_MODE`` is True. Still a real, valid PDF that carries the
legal footer on every page — so the §10.2 footer-parity contract holds even under the stub.
"""
from __future__ import annotations

from fpdf import FPDF
from kink import inject

from main.appodus_utils.integrations.report_pdf.interface import IReportPdfProvider
from main.appodus_utils.integrations.report_pdf.models import ReportPdfContext


def _latin1(text: str) -> str:
    return text.encode("latin-1", "replace").decode("latin-1")


@inject
class StubReportPdfProvider(IReportPdfProvider):
    @property
    def platform(self) -> str:
        return "STUB"

    def render(self, context: ReportPdfContext) -> bytes:
        pdf = FPDF(format="A4")
        pdf.set_compression(False)
        footer = _latin1(context.footer_text)

        def _footer() -> None:
            pdf.set_y(-18)
            pdf.set_font("Helvetica", "", 7)
            pdf.multi_cell(0, 3.4, footer, align="C")

        pdf.footer = _footer  # type: ignore[method-assign]
        # One page per section (plus the summary) so "footer on every page" is exercised.
        for title in ["Report", *[s.title for s in context.sections]]:
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 14)
            pdf.multi_cell(0, 8, _latin1(f"{title} — {context.vid}"))
        return bytes(pdf.output())
