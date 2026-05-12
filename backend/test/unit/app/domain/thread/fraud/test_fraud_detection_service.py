"""Unit tests for fraud detection rules (S38).

FraudDetectionService.scan() is a staticmethod that delegates to rules.scan() —
test the pure function directly, no mocks required.
"""
from __future__ import annotations

from main.app.domain.thread.fraud import rules


class TestPhonePattern:
    def test_international_number_triggers(self):
        matches = rules.scan("+2348012345678 please call me")
        assert "phone" in matches

    def test_spaced_number_triggers(self):
        matches = rules.scan("my number is 080 123 456 789")
        assert "phone" in matches

    def test_short_digit_sequence_does_not_trigger(self):
        matches = rules.scan("see page 123")
        assert "phone" not in matches


class TestEmailPattern:
    def test_email_triggers(self):
        matches = rules.scan("reach me at john@example.com")
        assert "email" in matches

    def test_no_email_in_clean_text(self):
        matches = rules.scan("The property survey is complete.")
        assert "email" not in matches


class TestUrlPattern:
    def test_http_url_triggers(self):
        matches = rules.scan("check http://example.com for details")
        assert "url" in matches

    def test_https_url_triggers(self):
        matches = rules.scan("visit https://survey.example.org")
        assert "url" in matches

    def test_no_url_in_clean_text(self):
        matches = rules.scan("The report is ready.")
        assert "url" not in matches


class TestBankingKeyword:
    def test_bvn_triggers(self):
        matches = rules.scan("Please provide your BVN to proceed")
        assert "banking" in matches

    def test_account_number_triggers(self):
        matches = rules.scan("Send to this account number: 123456")
        assert "banking" in matches

    def test_iban_triggers(self):
        matches = rules.scan("Use IBAN for the transfer")
        assert "banking" in matches

    def test_nin_triggers(self):
        matches = rules.scan("Your NIN is required")
        assert "banking" in matches


class TestOffPlatformPhrase:
    def test_whatsapp_me_triggers(self):
        matches = rules.scan("Please whatsapp me for details")
        assert "off_platform" in matches

    def test_contact_me_directly_triggers(self):
        matches = rules.scan("contact me directly to resolve this")
        assert "off_platform" in matches

    def test_call_me_at_triggers(self):
        matches = rules.scan("call me at this time")
        assert "off_platform" in matches


class TestCleanMessage:
    def test_clean_message_returns_empty(self):
        matches = rules.scan("The property inspection report is complete. All documents verified.")
        assert matches == []

    def test_empty_string_returns_empty(self):
        matches = rules.scan("")
        assert matches == []
