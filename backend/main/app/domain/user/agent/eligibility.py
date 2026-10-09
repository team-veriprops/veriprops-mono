"""Who may work a task of a role (PRD §11.2, §11.3, §3.3a, §16.1).

One rule, three callers: an agent accepting a task, an admin assigning one, and the admin's
suggested-agents ranking. An agent qualifies when:

- their agent application is APPROVED;
- the role is one an admin cleared, and the credential it needs is current (§3.3a: a lapsed
  credential suspends only the role it backs);
- for a location-bound role (Field, Surveyor), they cover the property's state — where the caller
  requires it. A pool accept and the ranking do; an admin's assignment does not, because sending an
  out-of-area agent is a deliberate remote job that carries the remote bonus (§20.1).

Capacity (`agent_max_active_tasks`) is checked separately by each caller, since it changes with
every accept.
"""
from __future__ import annotations

import enum
from datetime import date
from typing import Iterable, Optional

from kink import inject

from main.app.core.state.status import AgentRole
from main.app.domain.property.repo import PropertyRepo
from main.app.domain.user.agent.coverage.repo import AgentCoverageRepo
from main.app.domain.user.agent.credential.repo import AgentCredentialRepo
from main.app.domain.user.agent.credential.rules import active_roles
from main.app.domain.user.agent.profile.models import AgentApplicationStatus
from main.app.domain.user.agent.profile.repo import AgentProfileRepo
from main.appodus_utils import Utils

# Roles whose work happens at the property, so coverage must match its area (§16.1).
# Registry and Lawyer work is effectively remote.
LOCATION_BOUND_ROLES = frozenset({AgentRole.FIELD, AgentRole.SURVEYOR})


class Ineligibility(str, enum.Enum):
    """Why an agent may not work a task of a role."""

    NOT_APPROVED = "NOT_APPROVED"    # no approved agent application
    ROLE_INACTIVE = "ROLE_INACTIVE"  # role not cleared, or its credential lapsed/suspended
    OUT_OF_AREA = "OUT_OF_AREA"      # a location-bound role outside the agent's coverage


def covers_area(coverage: Iterable, area_state: Optional[str]) -> bool:
    """Whether any coverage row names *area_state*. An unknown area excludes no one."""
    if not area_state:
        return True
    target = area_state.strip().lower()
    return any((c.state or "").strip().lower() == target for c in coverage)


def ineligibility(
    profile, credentials: Iterable, coverage: Iterable, role: AgentRole, area_state: Optional[str],
    as_of: date, *, require_coverage: bool,
) -> Optional[Ineligibility]:
    """The first reason the agent may not work *role*, or None when they may."""
    if profile is None or profile.status != AgentApplicationStatus.APPROVED.value:
        return Ineligibility.NOT_APPROVED
    if role not in active_roles(profile.approved_roles or [], credentials, as_of):
        return Ineligibility.ROLE_INACTIVE
    if require_coverage and role in LOCATION_BOUND_ROLES and not covers_area(coverage, area_state):
        return Ineligibility.OUT_OF_AREA
    return None


@inject
class AgentEligibility:
    """Reads what `ineligibility` needs for one agent. Repositories only, so the task service
    and the reputation service can both depend on it without a cycle."""

    def __init__(
        self,
        profile_repo: AgentProfileRepo,
        credential_repo: AgentCredentialRepo,
        coverage_repo: AgentCoverageRepo,
        property_repo: PropertyRepo,
    ):
        self._profiles = profile_repo
        self._credentials = credential_repo
        self._coverage = coverage_repo
        self._properties = property_repo

    async def check(
        self, agent_id: str, role: AgentRole, property_id: Optional[str], *, require_coverage: bool,
    ) -> Optional[Ineligibility]:
        profile = await self._profiles.get_by_user_id(agent_id)
        if profile is None:
            return Ineligibility.NOT_APPROVED
        needs_area = require_coverage and role in LOCATION_BOUND_ROLES
        return ineligibility(
            profile,
            await self._credentials.list_for_user(agent_id),
            await self._coverage.list_for_user(agent_id) if needs_area else [],
            role,
            await self._properties.state_of(property_id) if needs_area else None,
            Utils.datetime_now().date(),
            require_coverage=require_coverage,
        )
