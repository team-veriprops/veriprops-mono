"""Listing-URL parser service.

Iterates registered parsers; falls back to ParseResultDto(success=False) on
any error or unsupported domain. Never raises to callers.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

from kink import di, inject

from main.app.domain.verification.parser.interface import ListingParser
from main.app.domain.verification.parser.models import ParseResultDto
from main.app.domain.verification.parser.providers.npc import NigeriaPropertyCentreParser
from main.app.domain.verification.parser.providers.propertypro import PropertyProParser

logger: Logger = di["logger"]

_REGISTERED_PARSERS: list[ListingParser] = [
    PropertyProParser(),
    NigeriaPropertyCentreParser(),
]


@inject
class ListingParserService:
    async def parse(self, url: str) -> ParseResultDto:
        for parser in _REGISTERED_PARSERS:
            if not parser.can_parse(url):
                continue
            try:
                data = await parser.parse(url)
                return ParseResultDto(success=True, data=data)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Listing parser failed for url={}: {}", url, exc)
                return ParseResultDto(
                    success=False,
                    error_message=f"Could not parse listing: {exc}",
                )
        return ParseResultDto(
            success=False,
            error_message="Listing URL is not from a supported source (PropertyPro, Nigeria Property Centre).",
        )
