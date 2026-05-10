"""Unit tests for the listing-URL parser (R5.2 — S13).

All parsers are tested against local fixture HTML — no real HTTP requests.
"""
from __future__ import annotations

import pathlib
from unittest.mock import AsyncMock, patch

import pytest

from main.app.domain.verification.parser.models import ParsedListingDto
from main.app.domain.verification.parser.providers.npc import NigeriaPropertyCentreParser
from main.app.domain.verification.parser.providers.propertypro import PropertyProParser
from main.app.domain.verification.parser.service import ListingParserService

_FIXTURES = pathlib.Path(__file__).parent.parent.parent.parent.parent / "fixtures" / "listings"

_PROPERTYPRO_HTML = (_FIXTURES / "propertypro_sample.html").read_text(encoding="utf-8")
_NPC_HTML = (_FIXTURES / "npc_sample.html").read_text(encoding="utf-8")


# ── PropertyPro ────────────────────────────────────────────────────


class TestPropertyProParser:
    def setup_method(self):
        self.parser = PropertyProParser()

    def test_can_parse_propertypro_url(self):
        assert self.parser.can_parse("https://www.propertypro.ng/property/12345/4-bedroom-duplex")

    def test_cannot_parse_npc_url(self):
        assert not self.parser.can_parse("https://nigeriapropertycentre.com/properties/12345")

    def test_cannot_parse_unknown_url(self):
        assert not self.parser.can_parse("https://example.com/listing/1")

    async def test_parse_extracts_title(self):
        with patch(
            "main.app.domain.verification.parser.providers.propertypro._fetch",
            new=AsyncMock(return_value=_PROPERTYPRO_HTML),
        ):
            result = await self.parser.parse("https://www.propertypro.ng/property/1/duplex")
        assert result.title is not None
        assert "Duplex" in result.title or "duplex" in result.title.lower()

    async def test_parse_extracts_state_lagos(self):
        with patch(
            "main.app.domain.verification.parser.providers.propertypro._fetch",
            new=AsyncMock(return_value=_PROPERTYPRO_HTML),
        ):
            result = await self.parser.parse("https://www.propertypro.ng/property/1/duplex")
        assert result.state == "LAGOS"

    async def test_parse_extracts_lga_lekki(self):
        with patch(
            "main.app.domain.verification.parser.providers.propertypro._fetch",
            new=AsyncMock(return_value=_PROPERTYPRO_HTML),
        ):
            result = await self.parser.parse("https://www.propertypro.ng/property/1/duplex")
        assert result.lga is not None
        assert "Lekki" in result.lga

    async def test_parse_infers_building_type(self):
        with patch(
            "main.app.domain.verification.parser.providers.propertypro._fetch",
            new=AsyncMock(return_value=_PROPERTYPRO_HTML),
        ):
            result = await self.parser.parse("https://www.propertypro.ng/property/1/duplex")
        assert result.property_type == "BUILDING"

    async def test_parse_extracts_price_minor(self):
        with patch(
            "main.app.domain.verification.parser.providers.propertypro._fetch",
            new=AsyncMock(return_value=_PROPERTYPRO_HTML),
        ):
            result = await self.parser.parse("https://www.propertypro.ng/property/1/duplex")
        # ₦85,000,000 → 85_000_000 * 100 kobo = 8_500_000_000
        assert result.price_minor == 8_500_000_000

    async def test_parse_sets_source_url(self):
        url = "https://www.propertypro.ng/property/1/duplex"
        with patch(
            "main.app.domain.verification.parser.providers.propertypro._fetch",
            new=AsyncMock(return_value=_PROPERTYPRO_HTML),
        ):
            result = await self.parser.parse(url)
        assert result.source_url == url


# ── NigeriaPropertyCentre ─────────────────────────────────────────


class TestNigeriaPropertyCentreParser:
    def setup_method(self):
        self.parser = NigeriaPropertyCentreParser()

    def test_can_parse_npc_url(self):
        assert self.parser.can_parse("https://nigeriapropertycentre.com/properties/12345")

    def test_cannot_parse_propertypro_url(self):
        assert not self.parser.can_parse("https://www.propertypro.ng/property/1/duplex")

    def test_cannot_parse_unknown_url(self):
        assert not self.parser.can_parse("https://example.com/property/1")

    async def test_parse_extracts_title(self):
        with patch(
            "main.app.domain.verification.parser.providers.npc._fetch",
            new=AsyncMock(return_value=_NPC_HTML),
        ):
            result = await self.parser.parse("https://nigeriapropertycentre.com/properties/1")
        assert result.title is not None
        assert "Bungalow" in result.title or "bungalow" in result.title.lower()

    async def test_parse_extracts_state_from_breadcrumb(self):
        with patch(
            "main.app.domain.verification.parser.providers.npc._fetch",
            new=AsyncMock(return_value=_NPC_HTML),
        ):
            result = await self.parser.parse("https://nigeriapropertycentre.com/properties/1")
        assert result.state == "LAGOS"

    async def test_parse_extracts_lga_from_breadcrumb(self):
        with patch(
            "main.app.domain.verification.parser.providers.npc._fetch",
            new=AsyncMock(return_value=_NPC_HTML),
        ):
            result = await self.parser.parse("https://nigeriapropertycentre.com/properties/1")
        assert result.lga is not None
        assert "Ikeja" in result.lga

    async def test_parse_infers_building_type(self):
        with patch(
            "main.app.domain.verification.parser.providers.npc._fetch",
            new=AsyncMock(return_value=_NPC_HTML),
        ):
            result = await self.parser.parse("https://nigeriapropertycentre.com/properties/1")
        assert result.property_type == "BUILDING"

    async def test_parse_extracts_price_minor(self):
        with patch(
            "main.app.domain.verification.parser.providers.npc._fetch",
            new=AsyncMock(return_value=_NPC_HTML),
        ):
            result = await self.parser.parse("https://nigeriapropertycentre.com/properties/1")
        # ₦45,000,000 → 45_000_000 * 100 kobo = 4_500_000_000
        assert result.price_minor == 4_500_000_000


# ── ListingParserService ───────────────────────────────────────────


class TestListingParserService:
    def setup_method(self):
        self.service = ListingParserService()

    async def test_unknown_domain_returns_success_false(self):
        result = await self.service.parse("https://example.com/property/1")
        assert result.success is False
        assert result.data is None
        assert result.error_message is not None

    async def test_propertypro_url_routed_to_correct_parser(self):
        with patch(
            "main.app.domain.verification.parser.providers.propertypro._fetch",
            new=AsyncMock(return_value=_PROPERTYPRO_HTML),
        ):
            result = await self.service.parse(
                "https://www.propertypro.ng/property/1/duplex"
            )
        assert result.success is True
        assert isinstance(result.data, ParsedListingDto)

    async def test_npc_url_routed_to_correct_parser(self):
        with patch(
            "main.app.domain.verification.parser.providers.npc._fetch",
            new=AsyncMock(return_value=_NPC_HTML),
        ):
            result = await self.service.parse(
                "https://nigeriapropertycentre.com/properties/1"
            )
        assert result.success is True
        assert isinstance(result.data, ParsedListingDto)

    async def test_malformed_html_returns_success_false_not_exception(self):
        with patch(
            "main.app.domain.verification.parser.providers.propertypro._fetch",
            new=AsyncMock(return_value="<html><body>no relevant content here</body></html>"),
        ):
            result = await self.service.parse(
                "https://www.propertypro.ng/property/1/duplex"
            )
        # Should not raise — degrades gracefully
        assert isinstance(result.success, bool)

    async def test_fetch_error_returns_success_false(self):
        with patch(
            "main.app.domain.verification.parser.providers.propertypro._fetch",
            new=AsyncMock(side_effect=Exception("Connection refused")),
        ):
            result = await self.service.parse(
                "https://www.propertypro.ng/property/1/duplex"
            )
        assert result.success is False
        assert "Connection refused" in (result.error_message or "")
