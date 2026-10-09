"""Who may work a task of a role (§11.2, §11.3, §3.3a, §16.1).

One rule, three callers: the agent accepting from the pool, the admin assigning, and the
suggested-agents ranking. An agent qualifies when their application is approved, the role is
one an admin cleared and its credential is current, and — for a location-bound role where the
caller requires it — they cover the property's state.
"""
from datetime import date
from types import SimpleNamespace

from main.app.core.state.status import AgentRole
from main.app.domain.user.agent.credential.models import CredentialStatus, CredentialType
from main.app.domain.user.agent.eligibility import Ineligibility, covers_area, ineligibility
from main.app.domain.user.agent.profile.models import AgentApplicationStatus

TODAY = date(2026, 10, 7)


def _profile(status=AgentApplicationStatus.APPROVED, approved=(AgentRole.FIELD,)):
    return SimpleNamespace(status=status.value, approved_roles=[r.value for r in approved])


def _check(profile, role=AgentRole.FIELD, *, credentials=(), coverage=("lagos",), area="Lagos",
           require_coverage=True):
    return ineligibility(
        profile, list(credentials), [SimpleNamespace(state=s) for s in coverage], role, area, TODAY,
        require_coverage=require_coverage,
    )


def test_an_approved_agent_with_the_role_in_area_qualifies():
    assert _check(_profile()) is None


def test_no_agent_profile_means_not_an_agent():
    assert _check(None) == Ineligibility.NOT_APPROVED


def test_a_pending_or_rejected_application_does_not_qualify():
    assert _check(_profile(AgentApplicationStatus.PENDING)) == Ineligibility.NOT_APPROVED
    assert _check(_profile(AgentApplicationStatus.REJECTED)) == Ineligibility.NOT_APPROVED


def test_a_role_the_admin_did_not_clear_does_not_qualify():
    assert _check(_profile(approved=(AgentRole.REGISTRY,)), AgentRole.FIELD) == Ineligibility.ROLE_INACTIVE


def test_a_role_whose_credential_lapsed_does_not_qualify():
    lawyer = _profile(approved=(AgentRole.LAWYER,))
    expired = SimpleNamespace(
        role=AgentRole.LAWYER.value, credential_type=CredentialType.NBA_LICENCE.value,
        status=CredentialStatus.VERIFIED.value, expiry_date=date(2026, 1, 1),
    )
    assert _check(lawyer, AgentRole.LAWYER, credentials=[expired]) == Ineligibility.ROLE_INACTIVE


def test_a_location_bound_role_outside_coverage_does_not_qualify_where_coverage_is_required():
    assert _check(_profile(), coverage=("abuja",)) == Ineligibility.OUT_OF_AREA
    # An admin may assign out of area on purpose (a remote job carries the remote bonus).
    assert _check(_profile(), coverage=("abuja",), require_coverage=False) is None


def test_remote_roles_are_never_gated_by_coverage():
    registry = _profile(approved=(AgentRole.REGISTRY,))
    assert _check(registry, AgentRole.REGISTRY, coverage=()) is None


def test_an_unknown_property_area_excludes_no_one():
    assert covers_area([], None) is True
    assert covers_area([SimpleNamespace(state=" Lagos ")], "lagos") is True
    assert covers_area([SimpleNamespace(state="Abuja")], "Lagos") is False
