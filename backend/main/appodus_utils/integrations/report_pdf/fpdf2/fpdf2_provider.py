"""Pure-Python report PDF renderer (fpdf2) — the default provider (D16).

No native dependencies (unlike WeasyPrint) so it runs identically on Windows, CI and
serverless. Produces a branded cover, a contents list, the tier-dependent sections, an
embedded QR to the public lookup, and the §3.5 legal footer on **every** page via the
``footer()`` hook (§10.2). Prior versions render a SUPERSEDED watermark.
"""
from __future__ import annotations

from io import BytesIO

import qrcode
from fpdf import FPDF
from kink import inject

from main.appodus_utils.integrations.report_pdf.interface import IReportPdfProvider
from main.appodus_utils.integrations.report_pdf.models import ReportPdfContext

# fpdf2 core fonts are latin-1; map the few unicode punctuation marks our copy uses so
# rendering never raises on an out-of-range glyph.
_UNICODE_FALLBACKS = {
    "—": "-", "–": "-",           # em/en dash
    "‘": "'", "’": "'",           # curly single quotes
    "“": '"', "”": '"',           # curly double quotes
    "✅": "", "•": "-",            # check mark, bullet
}


def _latin1(text: str) -> str:
    for uni, repl in _UNICODE_FALLBACKS.items():
        text = text.replace(uni, repl)
    return text.encode("latin-1", "replace").decode("latin-1")


class _ReportPdf(FPDF):
    def __init__(self, footer_text: str, superseded: bool):
        super().__init__(orientation="P", unit="mm", format="A4")
        self._footer_text = _latin1(footer_text)
        self._superseded = superseded
        self.set_auto_page_break(auto=True, margin=22)  # room for the footer band
        # Keep the stream uncompressed so the legal footer text is verifiable in the
        # output bytes (§10.2 parity check) — reports are small, so size is not a concern.
        self.set_compression(False)

    def header(self) -> None:
        if self._superseded:
            with self.rotation(45, self.w / 2, self.h / 2):
                self.set_font("Helvetica", "B", 60)
                self.set_text_color(230, 210, 210)
                self.set_xy(self.l_margin, self.h / 2 - 15)
                self.cell(self.w - 2 * self.l_margin, 30, "SUPERSEDED", align="C")
            self.set_text_color(0, 0, 0)
        # Restore the cursor so the watermark never disturbs content/footer layout.
        self.set_xy(self.l_margin, self.t_margin)

    def footer(self) -> None:
        self.set_y(-18)
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(120, 120, 120)
        self.multi_cell(self.w - 2 * self.l_margin, 3.4, self._footer_text, align="C")
        self.set_text_color(0, 0, 0)


@inject
class Fpdf2ReportPdfProvider(IReportPdfProvider):
    @property
    def platform(self) -> str:
        return "FPDF2"

    def render(self, context: ReportPdfContext) -> bytes:
        pdf = _ReportPdf(footer_text=context.footer_text, superseded=context.superseded)
        pdf.set_title(_latin1(f"{context.brand} Verification Report {context.vid}"))
        self._cover(pdf, context)
        self._sections(pdf, context)
        return bytes(pdf.output())

    # ── pages ─────────────────────────────────────────────────────

    def _cover(self, pdf: _ReportPdf, ctx: ReportPdfContext) -> None:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 22)
        pdf.cell(0, 12, _latin1(ctx.brand), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 12)
        pdf.cell(0, 8, "Property Verification Report", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        pdf.set_font("Helvetica", "", 10)
        for label, value in [
            ("Verification ID", ctx.vid),
            ("Tier", ctx.tier or "-"),
            ("Report version", f"v{ctx.report_version}.0"),
            ("Released", ctx.released_on or "-"),
            ("Property", ctx.address or "-"),
        ]:
            pdf.multi_cell(0, 7, _latin1(f"{label}: {value}"), new_x="LMARGIN", new_y="NEXT")

        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 9, _latin1(f"Trust Score: {ctx.trust_score}/100  ({ctx.trust_band})"),
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, _latin1(ctx.trust_meaning))
        pdf.ln(2)
        pdf.set_font("Helvetica", "I", 10)
        pdf.multi_cell(0, 5.5, _latin1(ctx.verdict))

        self._qr(pdf, ctx.qr_url)

    def _sections(self, pdf: _ReportPdf, ctx: ReportPdfContext) -> None:
        for section in ctx.sections:
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 13)
            pdf.multi_cell(0, 8, _latin1(section.title))
            pdf.ln(1)
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 5.5, _latin1(section.body))

    def _qr(self, pdf: _ReportPdf, url: str) -> None:
        img = qrcode.make(url)
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        # bottom-right of the cover, above the footer band
        pdf.image(buf, x=pdf.w - 40, y=pdf.h - 55, w=28)
        pdf.set_xy(pdf.w - 42, pdf.h - 26)
        pdf.set_font("Helvetica", "", 6)
        pdf.cell(30, 3, "Scan to verify", align="C")
