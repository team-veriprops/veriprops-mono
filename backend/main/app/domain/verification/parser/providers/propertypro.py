"""PropertyPro.ng listing parser.

Extracts property details from PropertyPro listing pages via HTML parsing.
Robust against layout changes — degrades to None fields rather than raising.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from main.app.domain.verification.parser.interface import ListingParser
from main.app.domain.verification.parser.models import ParsedListingDto

_FETCH_TIMEOUT = 15.0  # seconds

# Keyword → property_type mapping (checked against lowercased title).
_LAND_KEYWORDS = {"land", "plot", "acre", "hectare"}
_BUILDING_KEYWORDS = {"house", "duplex", "bungalow", "flat", "apartment", "terrace", "mansion", "studio"}

# "in LGA, State" trailing pattern.
_IN_LOCATION_RE = re.compile(r"\bin\s+([^,]+),\s+([^,\n]+)", re.IGNORECASE)
_BEDROOM_RE = re.compile(r"(\d+)\s*bedroom", re.IGNORECASE)
_PRICE_RE = re.compile(r"[₦₦NGN]?\s*([\d,]+(?:\.\d+)?)")


class PropertyProParser(ListingParser):
    def can_parse(self, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return "propertypro.ng" in host

    async def parse(self, url: str) -> ParsedListingDto:
        html = await _fetch(url)
        soup = BeautifulSoup(html, "html.parser")

        title = _extract_title(soup)
        price_minor = _extract_price(soup)
        state, lga = _extract_location_from_title(title) if title else (None, None)
        property_type = _infer_property_type(title)
        details = _extract_details(soup, title)

        return ParsedListingDto(
            property_type=property_type,
            state=state,
            lga=lga,
            address_line=_extract_address(soup, title),
            price_minor=price_minor,
            title=title,
            source_url=url,
            details=details,
        )


# ── Private helpers ────────────────────────────────────────────────


async def _fetch(url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; VeripropsBot/1.0; +https://veriprops.ng/bot)"
        ),
        "Accept": "text/html,application/xhtml+xml",
    }
    async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.text


def _extract_title(soup: BeautifulSoup) -> Optional[str]:
    # Try JSON-LD first.
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, dict) and data.get("name"):
                return str(data["name"]).strip()
        except (json.JSONDecodeError, TypeError):
            pass
    # og:title
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        return str(og["content"]).strip()
    # h1
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    return None


def _extract_price(soup: BeautifulSoup) -> Optional[int]:
    # og:price:amount
    meta = soup.find("meta", property="og:price:amount") or soup.find(
        "meta", attrs={"name": "price"}
    )
    if meta and meta.get("content"):
        raw = re.sub(r"[^\d.]", "", str(meta["content"]))
        if raw:
            return int(float(raw) * 100)

    # Elements that contain a Naira symbol or "NGN"
    for candidate in soup.find_all(
        True,
        class_=re.compile(r"price|amount|cost", re.I),
    ):
        text = candidate.get_text(separator=" ", strip=True)
        m = _PRICE_RE.search(text)
        if m:
            raw = re.sub(r"[,\s]", "", m.group(1))
            try:
                return int(float(raw) * 100)
            except ValueError:
                pass
    return None


def _extract_location_from_title(title: str) -> tuple[Optional[str], Optional[str]]:
    m = _IN_LOCATION_RE.search(title)
    if not m:
        return None, None
    lga = m.group(1).strip().title()
    state = m.group(2).strip().title()
    # Normalise well-known state names.
    return state.upper(), lga


def _extract_address(soup: BeautifulSoup, title: Optional[str]) -> Optional[str]:
    addr = soup.find("address")
    if addr:
        return addr.get_text(separator=" ", strip=True)
    # Try location/address labelled elements.
    for el in soup.find_all(True, class_=re.compile(r"address|location", re.I)):
        text = el.get_text(separator=" ", strip=True)
        if text:
            return text
    return title  # fallback: use title as human-readable address


def _infer_property_type(title: Optional[str]) -> Optional[str]:
    if not title:
        return None
    low = title.lower()
    for kw in _LAND_KEYWORDS:
        if kw in low:
            return "LAND"
    for kw in _BUILDING_KEYWORDS:
        if kw in low:
            return "BUILDING"
    return None


def _extract_details(soup: BeautifulSoup, title: Optional[str]) -> Optional[Dict[str, Any]]:
    details: Dict[str, Any] = {}
    # Bedrooms from title.
    if title:
        bm = _BEDROOM_RE.search(title)
        if bm:
            details["bedrooms"] = int(bm.group(1))
    # Try meta or labelled spans.
    for el in soup.find_all(
        True, attrs={"data-cy": re.compile(r"bedroom|bathroom|toilet|size|parking", re.I)}
    ):
        key = str(el.get("data-cy", "")).lower().replace("-", "_")
        val = el.get_text(strip=True)
        if val.isdigit():
            details[key] = int(val)
    return details or None
