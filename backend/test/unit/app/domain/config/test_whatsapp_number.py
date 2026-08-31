"""Unit tests for the official WhatsApp number projection (PRD §7.1.2, §7.4.1, S1).

The number is published in three places (site widget, certified reports, investor
materials), so it is derived from one setting and formatted in one place — these tests pin
both the wa.me-ready form and the human-readable form.
"""
from __future__ import annotations

from main.app.config.settings import settings
from main.app.domain.config.whatsapp_number import display_number, official_number_digits


class TestOfficialNumberDigits:
    def test_strips_everything_that_is_not_a_digit(self, monkeypatch):
        # wa.me accepts only digits — a stray '+' or space produces a broken deep link.
        monkeypatch.setattr(settings, "WHATSAPP_OFFICIAL_NUMBER", "+234 916 762 4347")
        assert official_number_digits() == "2349167624347"

    def test_passes_through_an_already_clean_number(self, monkeypatch):
        monkeypatch.setattr(settings, "WHATSAPP_OFFICIAL_NUMBER", "2349167624347")
        assert official_number_digits() == "2349167624347"

    def test_configured_default_is_the_published_number(self):
        # PRD §7.1.2 names +234 916 762 4347 as the one official number.
        assert official_number_digits() == "2349167624347"


class TestDisplayNumber:
    def test_groups_a_nigerian_number_as_published(self):
        assert display_number("2349167624347") == "+234 916 762 4347"

    def test_tolerates_decorated_input(self):
        assert display_number("+234-916-762-4347") == "+234 916 762 4347"

    def test_falls_back_to_plain_e164_for_an_unexpected_length(self):
        # Never guess at grouping for a shape we do not know — show it unambiguously.
        assert display_number("23491676") == "+23491676"

    def test_empty_number_yields_empty_string(self):
        assert display_number("") == ""
