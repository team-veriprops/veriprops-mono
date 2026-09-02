"""WhatsApp consent ledger (PRD §7.4.6, §7.8; D63/D64; WA-27).

The store behind §7.4.6's two opt-ins. It answers one question for the notification router
— *may we message this customer on WhatsApp?* — and records who asked and when, so the
§7.8 consent export is a query rather than a reconstruction.

Nothing here sends anything. Consent is read at the router (WA-16), never at a send site,
which is what makes "the customer never opted in" a single place to audit instead of a
rule every future milestone has to remember.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from kink import inject

from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.channel.whatsapp.consent.models import (
    CreateWhatsAppConsentDto,
    WhatsAppConsent,
    WhatsAppConsentDto,
    WhatsAppConsentKind,
    WhatsAppConsentSource,
)
from main.app.domain.channel.whatsapp.consent.repo import WhatsAppConsentRepo
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional

# Keyed on the account rather than the consent row, so the trail survives the row and
# reads as one history per customer.
_AUDIT_RESOURCE = "whatsapp_consent"


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class WhatsAppConsentService:
    def __init__(
        self,
        whatsapp_consent_repo: WhatsAppConsentRepo,
        audit_service: AuditLogService,
    ):
        self._whatsapp_consent_repo = whatsapp_consent_repo
        self._audit = audit_service

    # ── Reads ─────────────────────────────────────────────────────

    async def get_for_user(self, user_id: str) -> Optional[WhatsAppConsent]:
        return await self._whatsapp_consent_repo.get_by_user_id(user_id)

    async def describe(self, user_id: str) -> WhatsAppConsentDto:
        """What a consent surface renders. No row means both unticked, which is §7.4.6's
        required default — consent is never inherited from silence."""
        consent = await self._whatsapp_consent_repo.get_by_user_id(user_id)
        return self._to_dto(consent)

    async def utility_granted(self, user_id: str) -> bool:
        """**The milestone gate.** Read by the notification router before any §7.7 send."""
        consent = await self._whatsapp_consent_repo.get_by_user_id(user_id)
        return bool(consent and consent.utility)

    async def marketing_granted(self, user_id: str) -> bool:
        """The P1 audience gate. No sender uses it at v1 — marketing templates are drafted
        only when a consented campaign exists — but the state is captured from day one
        because an opt-in asked for later is an opt-in mostly not given."""
        consent = await self._whatsapp_consent_repo.get_by_user_id(user_id)
        return bool(consent and consent.marketing)

    # ── Writes ────────────────────────────────────────────────────

    async def set_consents(
        self,
        user_id: str,
        utility: bool,
        marketing: bool,
        source: WhatsAppConsentSource,
    ) -> WhatsAppConsentDto:
        """Record both §7.4.6 controls as the customer left them.

        Both are written every time because both are always shown together: a surface that
        sent only what changed would make an untouched control indistinguishable from one
        that was never rendered.
        """
        consent = await self._get_or_open(user_id)
        now = Utils.datetime_now()
        self._apply(consent, WhatsAppConsentKind.UTILITY, utility, source, now)
        self._apply(consent, WhatsAppConsentKind.MARKETING, marketing, source, now)
        self._record(user_id, source, utility=utility, marketing=marketing)
        return self._to_dto(consent)

    async def revoke_all(self, user_id: str, source: WhatsAppConsentSource) -> None:
        """STOP and its synonyms end both consents (D64).

        Utility and marketing go together here because the customer said "stop", not
        "stop some" — reading a blunt opt-out narrowly is how a channel earns a Meta
        quality-rating complaint.
        """
        consent = await self._get_or_open(user_id)
        now = Utils.datetime_now()
        self._apply(consent, WhatsAppConsentKind.UTILITY, False, source, now)
        self._apply(consent, WhatsAppConsentKind.MARKETING, False, source, now)
        self._record(user_id, source, utility=False, marketing=False)

    async def grant_utility(self, user_id: str, source: WhatsAppConsentSource) -> None:
        """START restores progress updates **only** (D64).

        Marketing needs a deliberate opt-in on the web: it is the consent §7.10 counts as a
        growth asset, so its record has to be worth counting — a one-word chat message is
        not the evidence a campaign audience should rest on.
        """
        consent = await self._get_or_open(user_id)
        now = Utils.datetime_now()
        self._apply(consent, WhatsAppConsentKind.UTILITY, True, source, now)
        self._record(user_id, source, utility=True, marketing=consent.marketing)

    # ── Internals ─────────────────────────────────────────────────

    async def _get_or_open(self, user_id: str) -> WhatsAppConsent:
        consent = await self._whatsapp_consent_repo.get_by_user_id(user_id)
        if consent is None:
            consent = await self._whatsapp_consent_repo.create_return_model(
                CreateWhatsAppConsentDto(user_id=user_id)
            )
        return consent

    def _apply(self, consent, kind, granted: bool, source, at) -> None:
        self._whatsapp_consent_repo.apply(consent, kind, granted, source, at)

    def _record(
        self, user_id: str, source: WhatsAppConsentSource, *, utility: bool, marketing: bool
    ) -> None:
        self._audit.schedule(
            AuditActionType.WHATSAPP_CONSENT_CHANGED,
            resource_type=_AUDIT_RESOURCE,
            resource_id=user_id,
            actor_id=user_id,
            details={"utility": utility, "marketing": marketing, "source": source.value},
        )

    @staticmethod
    def _to_dto(consent: Optional[WhatsAppConsent]) -> WhatsAppConsentDto:
        if consent is None:
            return WhatsAppConsentDto()
        return WhatsAppConsentDto(
            utility=consent.utility,
            marketing=consent.marketing,
            utility_updated_at=_latest(consent.utility_granted_at, consent.utility_revoked_at),
            marketing_updated_at=_latest(
                consent.marketing_granted_at, consent.marketing_revoked_at
            ),
        )


def _latest(*moments: Optional[datetime]) -> Optional[datetime]:
    """When this consent last moved — the newer of its two stamps, not whichever is set.

    A grant followed by a revoke has both, and showing the grant date beside "off" would
    read as a contradiction on the settings page.
    """
    known = [moment for moment in moments if moment is not None]
    return max(known) if known else None
