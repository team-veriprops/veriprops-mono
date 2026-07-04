"""Report PDF facade (§10.1/§10.2): both providers emit a valid PDF that carries the
legal footer on EVERY page (the §10.2 parity exit criterion), embed the QR, and render a
SUPERSEDED watermark on prior versions."""
import pytest

from main.appodus_utils.integrations.report_pdf.fpdf2.fpdf2_provider import Fpdf2ReportPdfProvider
from main.appodus_utils.integrations.report_pdf.stub.stub_provider import StubReportPdfProvider
from main.appodus_utils.integrations.report_pdf.models import ReportPdfContext, ReportPdfSection

# A unique word from the legal footer — appears exactly once per rendered page.
_FOOTER_MARKER = b"guarantee"


def _context(superseded=False):
    sections = [
        ReportPdfSection(title="Executive Summary", body="In our professional opinion, all clear."),
        ReportPdfSection(title="Registry & Title", body="Title search result: clean"),
        ReportPdfSection(title="Risk Summary", body="Overall trust score 95/100 (Safe)."),
    ]
    return ReportPdfContext(
        brand="Veriprops", vid="VP-2026-ABC", tier="STANDARD", address="12 Lekki Rd",
        report_version=1, released_on="04 Jul 2026", trust_score=95, trust_band="Safe",
        trust_meaning="Low risk.", verdict="In our professional opinion — proceed with normal diligence.",
        sections=sections,
        footer_text=(
            "This report represents a professional opinion, not a legal guarantee. "
            'Veriprops — Jurisdiction: Nigeria. "We reduce uncertainty. We do not eliminate it."'
        ),
        qr_url="https://veriprops.ng/verify/VP-2026-ABC", superseded=superseded,
    )


class TestFpdf2Provider:
    def test_valid_pdf_with_footer_on_every_page(self):
        out = Fpdf2ReportPdfProvider().render(_context())
        assert out[:4] == b"%PDF"
        pages = out.count(b"/Type /Page")  # excludes the single /Type /Pages tree node? guard below
        # cover + 3 sections = 4 content pages; footer marker appears once per page.
        assert out.count(_FOOTER_MARKER) == 4
        assert pages >= 4

    def test_embeds_qr_image(self):
        out = Fpdf2ReportPdfProvider().render(_context())
        assert b"/Image" in out or b"/XObject" in out

    def test_superseded_watermark(self):
        out = Fpdf2ReportPdfProvider().render(_context(superseded=True))
        assert b"SUPERSEDED" in out


class TestStubProvider:
    def test_valid_pdf_with_footer_on_every_page(self):
        out = StubReportPdfProvider().render(_context())
        assert out[:4] == b"%PDF"
        # stub renders 1 summary page + 3 section pages = 4 pages, footer on each.
        assert out.count(_FOOTER_MARKER) == 4
