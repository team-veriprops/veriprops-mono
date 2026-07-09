"""Unit tests for the legal-document content registry (S5 / PRD §3.5)."""
from __future__ import annotations

from main.app.domain.user.auth.consent.content import LEGAL_DOCUMENT_CONTENT
from main.app.domain.user.auth.consent.models import (
    ConsentDocumentType,
    ConsentSignoffStatus,
)


class TestLegalDocumentContentRegistry:
    def test_covers_every_consent_document_type(self):
        assert set(LEGAL_DOCUMENT_CONTENT.keys()) == set(ConsentDocumentType)

    def test_every_document_has_substantive_body(self):
        for content in LEGAL_DOCUMENT_CONTENT.values():
            assert content.title.strip()
            assert content.consent_version.strip()
            assert content.body and len(content.body) > 200, content.type

    def test_hrefs_are_legal_routes_and_unique(self):
        hrefs = [c.href for c in LEGAL_DOCUMENT_CONTENT.values()]
        assert all(h.startswith("/legal/") for h in hrefs)
        assert len(hrefs) == len(set(hrefs))

    def test_report_disclaimer_is_final_and_others_draft(self):
        for doc_type, content in LEGAL_DOCUMENT_CONTENT.items():
            if doc_type == ConsentDocumentType.REPORT_DISCLAIMER:
                assert content.signoff_status == ConsentSignoffStatus.FINAL
            else:
                assert content.signoff_status == ConsentSignoffStatus.DRAFT

    def test_registry_key_matches_entry_type(self):
        for doc_type, content in LEGAL_DOCUMENT_CONTENT.items():
            assert content.type == doc_type
