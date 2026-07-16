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
from sqlalchemy import update

from main.app.config.settings import settings
from main.app.domain.audit.models import AuditLog
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

        return surfaces
