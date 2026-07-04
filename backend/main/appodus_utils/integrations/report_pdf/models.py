"""Primitive render context for the report PDF facade (§10.1).

Deliberately domain-agnostic (plain values, no app DTOs) so the integration layer stays
decoupled from ``app.domain``. The report service maps its ``CustomerReportDto`` onto this.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ReportPdfSection:
    title: str
    body: str
    is_legal_opinion: bool = False


@dataclass
class ReportPdfContext:
    brand: str
    vid: str
    tier: Optional[str]
    address: Optional[str]
    report_version: int
    released_on: Optional[str]        # pre-formatted date string
    trust_score: int
    trust_band: str
    trust_meaning: str
    verdict: str
    sections: List[ReportPdfSection]
    footer_text: str                  # §3.5 legal footer — every page
    qr_url: str                       # public-lookup deep link encoded in the QR
    superseded: bool = False          # renders a watermark on every page
    extra: dict = field(default_factory=dict)
