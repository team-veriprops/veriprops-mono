"""Per-tier task composition + task-dependency config (PRD §4.2, §1.4).

Dependencies are **data, not hard-coded checks**: a tier declares which roles it
requires and which roles a given role depends on. The unlock rule is generic —
"are all upstream tasks ``SUBMITTED``?" — so adding/changing a dependency is
configuration, not code (it becomes admin-configurable in a later phase).

Key invariants enforced here:

- ``required_task_count`` is read from **tier config**, never from a
  ``COUNT(tasks)`` query, so a not-yet-instantiated Lawyer task is still counted
  (§2.5). A Premium verification needs all 4 roles approved to complete even
  though the Lawyer task only materialises after its siblings submit.
- The dependency graph is **acyclic**; cycles are rejected at config-load time
  (validated below for the built-in config, and exposed via
  :func:`validate_acyclic` for any admin-supplied config).
"""
from __future__ import annotations

from typing import Dict, Iterable, Tuple

from main.app.core.state.status import AgentRole, VerificationTier

# Roles required per tier, in canonical display order (PRD §1.4).
TIER_ROLES: Dict[VerificationTier, Tuple[AgentRole, ...]] = {
    VerificationTier.BASIC: (AgentRole.REGISTRY,),
    VerificationTier.STANDARD: (AgentRole.REGISTRY, AgentRole.FIELD, AgentRole.SURVEYOR),
    VerificationTier.PREMIUM: (AgentRole.REGISTRY, AgentRole.FIELD, AgentRole.SURVEYOR, AgentRole.LAWYER),
}

# role -> upstream roles that must all be SUBMITTED before role unlocks (§4.2).
# Only the Premium Lawyer task is dependency-blocked; everything else is free.
TASK_DEPENDENCIES: Dict[VerificationTier, Dict[AgentRole, Tuple[AgentRole, ...]]] = {
    VerificationTier.PREMIUM: {
        AgentRole.LAWYER: (AgentRole.REGISTRY, AgentRole.FIELD, AgentRole.SURVEYOR),
    },
}


def roles_for_tier(tier: VerificationTier) -> Tuple[AgentRole, ...]:
    """Return the ordered roles a tier requires."""
    return TIER_ROLES[VerificationTier(tier)]


def required_task_count(tier: VerificationTier) -> int:
    """Number of tasks a tier requires (from config, never ``COUNT(tasks)``).

    Basic → 1, Standard → 3, Premium → 4.
    """
    return len(roles_for_tier(tier))


def dependencies_for(tier: VerificationTier, role: AgentRole) -> Tuple[AgentRole, ...]:
    """Upstream roles ``role`` depends on for ``tier`` (empty tuple if none)."""
    return TASK_DEPENDENCIES.get(VerificationTier(tier), {}).get(AgentRole(role), ())


def blocking_roles(
    tier: VerificationTier,
    role: AgentRole,
    submitted_roles: Iterable[AgentRole],
) -> Tuple[AgentRole, ...]:
    """Upstream roles still blocking ``role`` (not yet in ``submitted_roles``).

    Drives the Lawyer "Awaiting other agents" UI: it lists the *actual* blockers.
    """
    submitted = {AgentRole(r) for r in submitted_roles}
    return tuple(dep for dep in dependencies_for(tier, role) if dep not in submitted)


def is_unlocked(
    tier: VerificationTier,
    role: AgentRole,
    submitted_roles: Iterable[AgentRole],
) -> bool:
    """True when every upstream dependency of ``role`` has SUBMITTED."""
    return not blocking_roles(tier, role, submitted_roles)


def validate_acyclic(dependencies: Dict[AgentRole, Tuple[AgentRole, ...]]) -> None:
    """Raise ``ValueError`` if the role-dependency graph contains a cycle.

    Trivial at four roles, but enforced so an admin-supplied config cannot
    deadlock the unlock check.
    """
    WHITE, GREY, BLACK = 0, 1, 2
    color: Dict[AgentRole, int] = {}

    def visit(node: AgentRole) -> None:
        color[node] = GREY
        for nxt in dependencies.get(node, ()):  # type: ignore[arg-type]
            state = color.get(nxt, WHITE)
            if state == GREY:
                raise ValueError(f"Cyclic task dependency detected at {nxt.value!r}")
            if state == WHITE:
                visit(nxt)
        color[node] = BLACK

    for role in dependencies:
        if color.get(role, WHITE) == WHITE:
            visit(role)


# Fail fast at import: the built-in dependency config must be acyclic.
for _tier_deps in TASK_DEPENDENCIES.values():
    validate_acyclic(_tier_deps)
