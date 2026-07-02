"""Credential-expiry & role-level suspension rules (PRD §3.3a).

Pure functions (no DB) so the "only that role is suspended" rule is unit-testable.
On expiry of a role's required credential, *only that role* is suspended — other
roles the agent holds are unaffected (a disbarred lawyer keeps a clean Field role).
"""
from __future__ import annotations

from datetime import date
from typing import Iterable, List, Protocol, Set

from main.app.core.state.status import AgentRole
from main.app.domain.user.agent.credential.models import (
    ROLE_REQUIRED_CREDENTIAL,
    CredentialStatus,
    CredentialType,
)


class _CredentialLike(Protocol):
    role: str
    credential_type: str
    status: str
    expiry_date: date | None


def is_credential_expired(expiry_date: date | None, as_of: date) -> bool:
    """A credential with an expiry is expired once that date has passed."""
    return expiry_date is not None and expiry_date < as_of


def _as_role(value) -> AgentRole:
    return value if isinstance(value, AgentRole) else AgentRole(value)


def suspended_roles(credentials: Iterable[_CredentialLike], as_of: date) -> Set[AgentRole]:
    """Roles whose required credential is expired or admin-suspended.

    A role backed by no credential type never appears here.
    """
    suspended: Set[AgentRole] = set()
    for cred in credentials:
        role = _as_role(cred.role)
        expired = is_credential_expired(cred.expiry_date, as_of)
        blocked = str(cred.status) in (
            CredentialStatus.EXPIRED.value,
            CredentialStatus.SUSPENDED.value,
        )
        if expired or blocked:
            suspended.add(role)
    return suspended


def active_roles(
    approved_roles: Iterable,
    credentials: Iterable[_CredentialLike],
    as_of: date,
) -> List[AgentRole]:
    """Approved roles the agent may currently work — approved minus suspended.

    A role that requires a credential but has none on file is also inactive.
    """
    blocked = suspended_roles(credentials, as_of)
    have_credential_for: Set[AgentRole] = {_as_role(c.role) for c in credentials}
    result: List[AgentRole] = []
    for role in (_as_role(r) for r in approved_roles):
        if role in blocked:
            continue
        required = ROLE_REQUIRED_CREDENTIAL.get(role)
        if required is not None and role not in have_credential_for:
            continue
        result.append(role)
    return result


def required_credential_for(role: AgentRole) -> CredentialType | None:
    return ROLE_REQUIRED_CREDENTIAL.get(role)
