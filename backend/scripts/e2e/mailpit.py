"""Mailpit reads for the stages that check real email delivery.

Mailpit captures every email in dev/local/test (SMTP :1025, HTTP API :8025). Mail is kept across
runs, so a check scopes its search to something this run created (an address, a VID).
"""
from __future__ import annotations

import time
from typing import Optional

import httpx

MAILPIT = "http://localhost:8025"


def mailpit_reachable() -> bool:
    try:
        httpx.get(f"{MAILPIT}/api/v1/messages", params={"limit": 1}, timeout=5).raise_for_status()
        return True
    except httpx.HTTPError:
        return False


def mailpit_total() -> Optional[int]:
    """How many messages Mailpit holds; None when it is unreachable."""
    try:
        return httpx.get(f"{MAILPIT}/api/v1/messages", params={"limit": 1},
                         timeout=10).json().get("total", 0)
    except httpx.HTTPError:
        return None


def search_mail(query: str) -> list[dict]:
    """Messages matching a Mailpit search *query*, newest first."""
    r = httpx.get(f"{MAILPIT}/api/v1/search", params={"query": query}, timeout=10)
    return r.json().get("messages") or []


def count_mail(query: str) -> int:
    """How many messages match *query*; -1 when Mailpit cannot be read."""
    try:
        return len(search_mail(query))
    except httpx.HTTPError:
        return -1


def message_text(message_id: str) -> str:
    """One message's HTML and plain-text bodies, joined."""
    body = httpx.get(f"{MAILPIT}/api/v1/message/{message_id}", timeout=10).json()
    return (body.get("HTML") or "") + (body.get("Text") or "")


def wait_for_mail(query: str, timeout_s: float = 15.0) -> list[dict]:
    """Messages matching *query*, polled until one arrives or *timeout_s* passes."""
    deadline = time.monotonic() + timeout_s
    while True:
        found = search_mail(query)
        if found or time.monotonic() >= deadline:
            return found
        time.sleep(0.5)
