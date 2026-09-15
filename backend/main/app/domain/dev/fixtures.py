"""People builders shared by the dev seed and the lifecycle scenario builder (non-prod only).

Both create login-able accounts directly rather than through signup: identity is not the
behaviour under test, and signup's email-OTP gate has no place in a fixture. Everything that
*is* under test — verifications, tasks, payments, review, release — goes through the real
services (see ``scenario.py``).
"""
from __future__ import annotations

import secrets
from datetime import datetime
from typing import Dict, Iterable

from sqlalchemy import text

from main.app.config.settings import settings
from main.app.core.state.status import AgentRole
from main.app.domain.user.agent.coverage.models import AgentCoverage
from main.app.domain.user.agent.credential.models import (
    ROLE_REQUIRED_CREDENTIAL,
    AgentCredential,
    CredentialStatus,
)
from main.app.domain.user.agent.profile.models import AgentProfile
from main.app.domain.user.auth.consent.models import REQUIRED_SIGNUP_CONSENTS, UserConsent
from main.app.domain.user.auth.session.models import UserType
from main.app.domain.user.models import User
from main.appodus_utils import Utils

# The password every QA account shares (non-prod only).
QA_PASSWORD = "Test1234!"
# A non-special-use domain — the email validator rejects reserved TLDs like `.test`.
QA_EMAIL_DOMAIN = "veriprops.io"


def new_entity(model, **fields):
    """Construct a BaseEntity row with the audit bookkeeping the repos set on create.

    ``id`` is a real ``UUID`` (not a str) so SQLAlchemy's insertmanyvalues sentinel
    matching lines up with what asyncpg returns."""
    obj = model(**fields)
    obj.id = Utils.generate_uuid()
    obj.version = 1
    obj.deleted = False
    obj.date_created = Utils.datetime_now()
    return obj


def seeded_agent_email(role: AgentRole) -> str:
    """The deterministic email of the seeded agent for *role*."""
    return f"qa-agent-{role.value.lower()}@{QA_EMAIL_DOMAIN}"


def unique_qa_email(prefix: str) -> str:
    """A QA email no other fixture holds, so parallel scenarios never collide."""
    return f"{prefix}-{secrets.token_hex(4)}@{QA_EMAIL_DOMAIN}"


def unique_local_phone() -> str:
    """A Nigerian local number unique to one fixture.

    Sharing a verified phone across accounts is the §17.1 anti-farming signal, so a fixture
    that reused one would quietly void any referral behaviour a spec asserts on."""
    return f"81{secrets.randbelow(10 ** 8):08d}"


def add_verified_user(
    session, *, first_name: str, last_name: str, email: str, phone_local: str,
    persona: str, password: str = QA_PASSWORD,
) -> User:
    """A login-able user with verified email + phone — the state signup and the payment
    step's phone gate leave a real customer or agent in."""
    user = new_entity(
        User,
        first_name=first_name, last_name=last_name,
        email=email, email_normalized=email, email_verified=True,
        phone_country_code="NG", phone_dial_code="+234", phone=phone_local,
        phone_e164=f"+234{phone_local}", phone_verified=True,
        country_of_residence="NG", timezone="Africa/Lagos", preferred_currency="NGN",
        user_type=UserType.USER.value, personas=[persona], trust_status="TRUSTED",
        password_hash=Utils.get_password_hash(password),
    )
    session.add(user)
    return user


def add_approved_agent(
    session, role: AgentRole, *, email: str, phone_local: str, now: datetime,
    password: str = QA_PASSWORD,
) -> User:
    """An agent an admin can assign *role* work to straight away: APPROVED profile,
    Lagos coverage (§16), and — for credentialed roles (§3.3a) — a VERIFIED licence, without
    which the role is inactive and the agent never ranks in suggestions."""
    agent = add_verified_user(
        session, first_name=role.value.title(), last_name="Agent", email=email,
        phone_local=phone_local, persona="AGENT", password=password,
    )
    session.add(new_entity(
        AgentProfile,
        user_id=str(agent.id), roles=[role.value], approved_roles=[role.value],
        status="APPROVED", availability="GREEN", submitted_at=now, reviewed_at=now,
    ))
    session.add(new_entity(AgentCoverage, user_id=str(agent.id), state="lagos", lga="eti-osa"))
    required_credential = ROLE_REQUIRED_CREDENTIAL.get(role)
    if required_credential is not None:
        session.add(new_entity(
            AgentCredential,
            user_id=str(agent.id), role=role.value,
            credential_type=required_credential.value,
            licence_number=f"QA-{role.value}-{secrets.token_hex(3).upper()}",
            expiry_date=Utils.datetime_now_plus(days=365).date(),
            status=CredentialStatus.VERIFIED.value,
        ))
    return agent


async def current_consent_versions(session) -> Dict[str, str]:
    """The current version of every required signup consent, read from
    ``consent_documents`` — accepting a superseded version still counts as missing."""
    required = {t.value for t in REQUIRED_SIGNUP_CONSENTS}
    rows = (await session.execute(text(
        "SELECT type, consent_version FROM consent_documents ORDER BY effective_at DESC"
    ))).all()
    current: Dict[str, str] = {}
    for row in rows:
        if row.type in required and row.type not in current:
            current[row.type] = row.consent_version
    return current


async def record_required_consents(
    session, user_ids: Iterable[str], now: datetime, *, include_super_admin: bool,
) -> None:
    """Accept the current version of every required consent for each user.

    Fixture users bypass ``AuthService.signup`` — the only path that normally records
    consents. Without these rows every one of them looks like an account with outdated
    terms and is held behind the **non-dismissible** re-acceptance modal (§3.2) on every
    authenticated page, which blocks UI automation outright.

    The super-admin survives ``reset()`` and is inserted by migration ``0001``, so the seed
    covers it too (*include_super_admin*); a scenario must not, or every call would stack
    another set of acceptances onto the same account.
    """
    current = await current_consent_versions(session)
    all_ids = list(user_ids)
    if include_super_admin:
        admin_row = (await session.execute(
            text("SELECT id FROM users WHERE email = :email LIMIT 1"),
            {"email": settings.SUPER_ADMIN_EMAIL},
        )).first()
        if admin_row:
            all_ids.append(str(admin_row.id))

    for user_id in all_ids:
        for document_type, consent_version in current.items():
            session.add(new_entity(
                UserConsent,
                user_id=user_id, document_type=document_type,
                consent_version=consent_version, accepted_at=now,
            ))
