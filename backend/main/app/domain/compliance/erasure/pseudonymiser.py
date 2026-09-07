"""PII pseudonymiser (PRD §4.11, §19).

Carries out an approved erasure by replacing the data subject's *identifying* PII
with a **stable opaque token** across the identity, authentication, audit and KYC
surfaces — never by deleting rows. This satisfies the NDPA erasure right while
preserving a defensible audit/consent trail (the transition events stay intact,
only the actor identity is severed, §4.11).

The token is deterministic per subject (salted by the deployment secret), so the
same person always pseudonymises to the same value — repeated executes are a no-op
and cross-record correlation for a legitimate re-identification request stays
possible while the raw PII is gone.

Runs inside the caller's transaction: it reads the request-scoped session from
context (sanctioned for transactional service code) and issues bulk UPDATEs.
"""
from __future__ import annotations

import hashlib
from typing import List

from kink import inject
from sqlalchemy import or_, select, update

from main.app.config.settings import settings
from main.app.domain.audit.models import AuditLog
from main.app.domain.channel.whatsapp.bot.session.models import WhatsAppBotSession
from main.app.domain.channel.whatsapp.handoff.models import HandoffTokenRedemption
from main.app.domain.channel.whatsapp.inbound.models import WhatsAppInboundMessage
from main.app.domain.channel.whatsapp.link.models import (
    WhatsAppLink,
    WhatsAppLinkStatus,
)
from main.app.domain.verification.delegate.models import CaseDelegate
from main.app.domain.payout.bank_account.models import AgentBankAccount
from main.app.domain.user.agent.kyc.models import KycRecord
from main.app.domain.user.auth.oauth.models import OAuthIdentity
from main.app.domain.user.auth.session.models import DeviceSession, SecurityEvent
from main.app.domain.user.auth.consent.models import UserConsent
from main.app.domain.user.models import User
from main.appodus_utils import Utils
from main.appodus_utils.db.session import get_db_session_from_context
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger

_REDACTED = "[erased]"


# TODO(gap): secondary-PII scope — card fingerprints, third-party share-recipient emails,
# and property addresses are not scrubbed yet; each needs its own retention basis —
# PRD "Known Gaps & Roadmap".
@inject
@decorate_all_methods(method_trace_logger, exclude=["__init__", "token_for"], exclude_startswith=["_"])
class PiiPseudonymiser:
    def token_for(self, subject_user_id: str) -> str:
        """Deterministic, non-reversible opaque token for a subject (§4.11)."""
        digest = hashlib.sha256(
            f"{subject_user_id}:{settings.AUTHJWT_SECRET_KEY}".encode("utf-8")
        ).hexdigest()[:16]
        return f"erased-{digest}"

    async def pseudonymise(self, subject_user_id: str, token: str) -> List[str]:
        """Scrub identifying PII for the subject to ``token`` across every surface.

        Returns the list of surfaces touched (recorded in the erasure audit event).
        The subject's own user id is the 36-char string form (the JWT subject /
        audit actor form); agent-owned tables key on the same id.
        """
        session = get_db_session_from_context()
        surfaces: List[str] = []

        # 1) Identity — name/email/phone/avatar cleared; credentials destroyed so the
        #    account can never authenticate again. email_normalized stays unique via the token.
        await session.execute(
            update(User)
            .where(User.id == subject_user_id)
            .values(
                first_name=_REDACTED,
                last_name=_REDACTED,
                email=f"{token}@erased.invalid",
                email_normalized=f"{token}@erased.invalid",
                email_verified=False,
                phone=_REDACTED,
                phone_e164=None,
                phone_verified=False,
                avatar_url=None,
                password_hash=None,
            )
        )
        surfaces.append("users")

        # 2) Audit actor identity severed, IP dropped — the events themselves are retained (§4.11).
        await session.execute(
            update(AuditLog)
            .where(AuditLog.actor_id == subject_user_id)
            .values(actor_id=token, ip_address=None)
        )
        surfaces.append("audit_logs")

        # 3) Sessions — device/IP/fingerprint scrubbed and every session revoked.
        await session.execute(
            update(DeviceSession)
            .where(DeviceSession.user_id == subject_user_id)
            .values(
                device=_REDACTED, browser=None, os=None,
                ip_address=None, approx_location=None, device_fingerprint=None,
                revoked=True, revoked_at=Utils.datetime_now(),
            )
        )
        surfaces.append("device_sessions")

        # 4) Security activity history — tracking PII scrubbed, the events retained.
        await session.execute(
            update(SecurityEvent)
            .where(SecurityEvent.user_id == subject_user_id)
            .values(ip_address=None, approx_location=None, device=None, device_fingerprint=None)
        )
        surfaces.append("security_events")

        # 5) Consent snapshots — the acceptance record is retained; only the IP/fingerprint go.
        await session.execute(
            update(UserConsent)
            .where(UserConsent.user_id == subject_user_id)
            .values(ip_address=None, device_fingerprint=None)
        )
        surfaces.append("user_consents")

        # 6) Social identity.
        await session.execute(
            update(OAuthIdentity)
            .where(OAuthIdentity.user_id == subject_user_id)
            .values(email=None, raw_profile=None)
        )
        surfaces.append("oauth_identities")

        # 7) KYC — the provider reference (never raw biometrics) is severed.
        await session.execute(
            update(KycRecord)
            .where(KycRecord.user_id == subject_user_id)
            .values(provider_ref=token)
        )
        surfaces.append("kyc_records")

        # 8) Agent bank details (financial PII of the subject).
        await session.execute(
            update(AgentBankAccount)
            .where(AgentBankAccount.agent_id == subject_user_id)
            .values(bank_name=_REDACTED, account_number=_REDACTED, account_name=_REDACTED)
        )
        surfaces.append("agent_bank_accounts")

        # 9-13) The WhatsApp channel (§26.8).
        surfaces += await self._pseudonymise_whatsapp(session, subject_user_id, token)

        return surfaces

    async def _pseudonymise_whatsapp(
        self, session, subject_user_id: str, token: str
    ) -> List[str]:
        """Sever the subject's identity across the WhatsApp channel (§26.8, NDPA).

        The channel keys almost everything on a **phone number** rather than a user id, so
        this starts by reading the subject's linked numbers and then scrubs by number. It
        has to run before the link rows are cleared, which is why it is one method rather
        than five more blocks above.

        The line drawn here is §26.8's own: **identity is severed, content is retained.**
        Chat logs are retained business records covered by the same access controls as case
        data, so what a customer said stays; the number that said it, the profile name Meta
        supplied, and the raw envelope carrying both do not. That is the same split as
        `audit_logs` above, where the actor is severed and the events stay intact.
        """
        surfaces: List[str] = []

        # The subject's numbers, read before the link rows are cleared. Includes revoked
        # links, whose rows keep no number — hence the null filter.
        rows = await session.execute(
            select(WhatsAppLink.phone_e164).where(
                WhatsAppLink.user_id == subject_user_id,
                WhatsAppLink.phone_e164.is_not(None),
            )
        )
        phones = [phone for (phone,) in rows.all() if phone]

        # 9) The link itself. The number is cleared to NULL rather than tokenised, because
        # `phone_e164` is uniquely constrained and a retained value would hold that
        # constraint forever — locking a real number out of every future account. This is
        # the same reasoning as `WhatsAppLinkRepo.release_number`.
        await session.execute(
            update(WhatsAppLink)
            .where(WhatsAppLink.user_id == subject_user_id)
            .values(
                phone_e164=None,
                wa_id=None,
                status=WhatsAppLinkStatus.REVOKED.value,
                revoked_reason="erasure",
            )
        )
        surfaces.append("whatsapp_links")

        if not phones:
            # Never linked a number: nothing downstream keys on this subject.
            return surfaces

        # 10) Bot session. `context` is dropped outright rather than tokenised — it holds
        # the free-text answers of a half-finished chat intake (a property address, a
        # landmark), which is personal data that never became a business record because the
        # case was never created.
        await session.execute(
            update(WhatsAppBotSession)
            .where(WhatsAppBotSession.phone_e164.in_(phones))
            .values(phone_e164=token, context=None)
        )
        surfaces.append("whatsapp_bot_sessions")

        # 11) The inbound journal. `from_phone` is 20 characters and the subject token is
        # 23, so it takes the flat redaction; re-identification still works through
        # `chat_message_id`, whose conversation carries the (stable) user id. `payload` is
        # Meta's raw envelope — it duplicates the normalized columns and carries the number
        # and profile name besides, so it goes rather than being picked apart.
        await session.execute(
            update(WhatsAppInboundMessage)
            .where(WhatsAppInboundMessage.from_phone.in_(phones))
            .values(from_phone=_REDACTED, sender_name=_REDACTED, payload=None)
        )
        surfaces.append("whatsapp_inbound_messages")

        # 12) Delegations the subject holds on **other people's** cases (§26.4.5). Revoked
        # as well as scrubbed: a grant addressed to a number nobody can reach any more is
        # not a grant, and leaving it live would keep the case's delegate slot occupied.
        # Delegates on the subject's *own* cases are other people, and their erasure is
        # their own request to make.
        await session.execute(
            update(CaseDelegate)
            .where(CaseDelegate.phone_e164.in_(phones))
            .values(
                name=_REDACTED,
                phone_e164=token,
                revoked_at=Utils.datetime_now(),
                revoked_reason="erasure",
            )
        )
        surfaces.append("case_delegates")

        # 13) The §26.5 handoff ledger. The jti rows stay — they are what makes a token
        # single-use, and dropping them would let a captured link be replayed — but the
        # number and the redeeming IP are identity, not enforcement.
        await session.execute(
            update(HandoffTokenRedemption)
            .where(
                or_(
                    HandoffTokenRedemption.customer_id == subject_user_id,
                    HandoffTokenRedemption.phone_e164.in_(phones),
                )
            )
            .values(phone_e164=token, redeemed_ip=None)
        )
        surfaces.append("handoff_token_redemptions")

        return surfaces
