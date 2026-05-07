"""NigeriaPropertyCentre.com listing parser.

Extracts property details from NigeriaPropertyCentre listing pages.
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

_FETCH_TIMEOUT = 15.0

_LAND_KEYWORDS = {"land", "plot", "acre", "hectare"}
_BUILDING_KEYWORDS = {"house", "duplex", "bungalow", "flat", "apartment", "terrace", "mansion", "studio", "detached", "semi-detached"}

_PRICE_RE = re.compile(r"[₦NGN]?\s*([\d,]+(?:\.\d+)?)")
_BEDROOM_RE = re.compile(r"(\d+)\s*bed(?:room)?s?", re.IGNORECASE)
_IN_LOCATION_RE = re.compile(r"\bin\s+([^,]+),\s+([^,\n]+)", re.IGNORECASE)

# Generic breadcrumb root segments to skip.
_SKIP_BREADCRUMBS = {"home", "nigeria", "properties", "buy", "rent", "all"}


class NigeriaPropertyCentreParser(ListingParser):
    def can_parse(self, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return "nigeriapropertycentre.com" in host

    async def parse(self, url: str) -> ParsedListingDto:
        html = await _fetch(url)
        soup = BeautifulSoup(html, "html.parser")

        title = _extract_title(soup)
        price_minor = _extract_price(soup)
        state, lga = _extract_location(soup, title)
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
    # Try JSON-LD.
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
    # h1 with class containing "listing" or "property"
    for h1 in soup.find_all("h1"):
        text = h1.get_text(strip=True)
        if text:
            return text
    return None


def _extract_price(soup: BeautifulSoup) -> Optional[int]:
    # NPC often puts price in a <span> with class "price" or similar
    for el in soup.find_all(
        True,
        class_=re.compile(r"price|amount|listing-price", re.I),
    ):
        text = el.get_text(separator=" ", strip=True)
        m = _PRICE_RE.search(text)
        if m:
            raw = re.sub(r"[,\s]", "", m.group(1))
            try:
                return int(float(raw) * 100)
            except ValueError:
                pass
    # Try meta
    for attr in ("og:price:amount", "price"):
        meta = soup.find("meta", property=attr) or soup.find("meta", attrs={"name": attr})
        if meta and meta.get("content"):
            raw = re.sub(r"[^\d.]", "", str(meta["content"]))
            if raw:
                return int(float(raw) * 100)
    return None


def _extract_location(soup: BeautifulSoup, title: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    # NPC breadcrumbs: Home > State > LGA > ...
    # Use the deepest element with "breadcrumb" in its class (ol/ul preferred over nav).
    breadcrumb_el = None
    for tag in ("ol", "ul", "nav", "div"):
        el = soup.find(tag, class_=re.compile(r"breadcrumb", re.I))
        if el:
            breadcrumb_el = el
            break
    if breadcrumb_el:
        crumbs = [
            a.get_text(strip=True)
            for a in breadcrumb_el.find_all("a")
            if a.get_text(strip=True).lower() not in _SKIP_BREADCRUMBS
        ]
        if len(crumbs) >= 2:
            return crumbs[0].upper(), crumbs[1].title()

    # Try meta location tags
    for name in ("geo.region", "geo.placename", "location"):
        meta = soup.find("meta", attrs={"name": name})
        if meta and meta.get("content"):
            parts = str(meta["content"]).split(",")
            if len(parts) >= 2:
                return parts[0].strip().upper(), parts[1].strip().title()

    # Fall back: parse title
    if title:
        m = _IN_LOCATION_RE.search(title)
        if m:
            return m.group(2).strip().upper(), m.group(1).strip().title()
    return None, None


def _extract_address(soup: BeautifulSoup, title: Optional[str]) -> Optional[str]:
    addr = soup.find("address")
    if addr:
        return addr.get_text(separator=" ", strip=True)
    for el in soup.find_all(True, class_=re.compile(r"address|location|area", re.I)):
        text = el.get_text(separator=" ", strip=True)
        if 5 < len(text) < 200:
            return text
    return title


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
    if title:
        bm = _BEDROOM_RE.search(title)
        if bm:
            details["bedrooms"] = int(bm.group(1))
    for el in soup.find_all(
        True,
        attrs={"data-label": re.compile(r"bed|bath|toilet|parking|size|sqm", re.I)},
    ):
        key = str(el.get("data-label", "")).lower().replace(" ", "_")
        val = el.get_text(strip=True)
        if val.isdigit():
            details[key] = int(val)
    return details or None
