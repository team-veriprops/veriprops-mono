"""Abstract listing parser interface."""
from __future__ import annotations

from abc import ABC, abstractmethod

from main.app.domain.verification.parser.models import ParsedListingDto


class ListingParser(ABC):
    @abstractmethod
    def can_parse(self, url: str) -> bool:
        """Return True if this parser handles the given URL."""

    @abstractmethod
    async def parse(self, url: str) -> ParsedListingDto:
        """Fetch and parse the listing at *url*.

        Raise any exception on failure — the service wraps all calls in
        try/except and converts them to ParseResultDto(success=False).
        """
