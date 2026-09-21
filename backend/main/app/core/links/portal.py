"""The customer portal's routes, as the backend builds them (PRD §12.2, §16.7, §26.4.2).

A mirror of `frontend/src/lib/routes.ts` `ROUTES.PORTAL`, kept in one place so a notification,
a WhatsApp template and the portal assistant can never point at three spellings of the same
page. Two forms, because two kinds of reader exist:

* **relative** paths for in-app links, which the frontend resolves against its own origin;
* **absolute** URLs for anything read outside the app — a WhatsApp message, a chat reply
  copied elsewhere — built on `PUBLIC_APP_BASE_URL`.

When a portal route moves, change it here and in `routes.ts` in the same change.
"""
from __future__ import annotations

import enum
from typing import Optional

from main.app.config.settings import settings

_VERIFICATIONS = "/portal/verifications"


class VerificationPage(str, enum.Enum):
    """The pages under one verification — the path segment after its id."""

    PAY = "pay"
    EVIDENCE = "evidence"
    REPORT = "report"
    MESSAGES = "messages"
    ACTIVITY = "activity"
    CONFIRMED = "confirmed"


def verification_path(verification_ref: str, page: Optional[VerificationPage] = None) -> str:
    """One verification's page, or its detail page when *page* is omitted."""
    base = f"{_VERIFICATIONS}/{verification_ref}"
    return f"{base}/{page.value}" if page else base


def new_verification_path() -> str:
    """The submission wizard, which resumes the customer's open draft if they have one."""
    return f"{_VERIFICATIONS}/new"


def absolute_url(path: str) -> str:
    """*path* on the public app origin, for a link read outside the app."""
    return f"{settings.PUBLIC_APP_BASE_URL.rstrip('/')}{path}"
