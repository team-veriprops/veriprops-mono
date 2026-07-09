"""Role-level credential-expiry suspension (PRD §3.3a) — pure, no DB.

Only the role whose required credential expired is suspended; other roles the
agent holds are unaffected (a disbarred lawyer keeps a clean Field role).
"""
from datetime import date
from types import SimpleNamespace

from main.app.core.state.status import AgentRole
from main.app.domain.user.agent.credential.models import CredentialStatus, CredentialType
from main.app.domain.user.agent.credential.rules import (
    active_roles,
    is_credential_expired,
    required_credential_for,
    suspended_roles,
)

TODAY = date(2026, 7, 2)


def _cred(role, *, expiry=None, status=CredentialStatus.VERIFIED):
    return SimpleNamespace(
        role=role.value if isinstance(role, AgentRole) else role,
        credential_type=CredentialType.NBA_LICENCE.value,
        status=status.value,
        expiry_date=expiry,
    )


class TestExpiry:
    def test_expired_when_past(self):
        assert is_credential_expired(date(2026, 7, 1), TODAY) is True

    def test_not_expired_when_future_or_none(self):
        assert is_credential_expired(date(2026, 7, 3), TODAY) is False
        assert is_credential_expired(None, TODAY) is False


class TestSuspension:
    def test_only_expired_role_is_suspended(self):
        creds = [
            _cred(AgentRole.LAWYER, expiry=date(2026, 6, 1)),   # expired
            _cred(AgentRole.SURVEYOR, expiry=date(2027, 1, 1)),  # valid
        ]
        suspended = suspended_roles(creds, TODAY)
        assert AgentRole.LAWYER in suspended
        assert AgentRole.SURVEYOR not in suspended

    def test_admin_suspended_status_counts(self):
        creds = [_cred(AgentRole.LAWYER, status=CredentialStatus.SUSPENDED)]
        assert AgentRole.LAWYER in suspended_roles(creds, TODAY)


class TestActiveRoles:
    def test_disbarred_lawyer_keeps_field_role(self):
        approved = [AgentRole.FIELD, AgentRole.LAWYER]
        creds = [_cred(AgentRole.LAWYER, expiry=date(2026, 6, 1))]  # NBA licence expired
        active = active_roles(approved, creds, TODAY)
        assert AgentRole.FIELD in active      # no credential required, stays active
        assert AgentRole.LAWYER not in active  # suspended by expiry

    def test_role_requiring_credential_with_none_is_inactive(self):
        # Approved for SURVEYOR but no surveyor licence on file → inactive.
        active = active_roles([AgentRole.SURVEYOR], [], TODAY)
        assert AgentRole.SURVEYOR not in active

    def test_credential_free_roles_active_without_credentials(self):
        active = active_roles([AgentRole.FIELD, AgentRole.REGISTRY], [], TODAY)
        assert set(active) == {AgentRole.FIELD, AgentRole.REGISTRY}


class TestRequiredCredential:
    def test_surveyor_and_lawyer_require_licences(self):
        assert required_credential_for(AgentRole.SURVEYOR) == CredentialType.SURVEYOR_LICENCE
        assert required_credential_for(AgentRole.LAWYER) == CredentialType.NBA_LICENCE

    def test_field_and_registry_require_none(self):
        assert required_credential_for(AgentRole.FIELD) is None
        assert required_credential_for(AgentRole.REGISTRY) is None
