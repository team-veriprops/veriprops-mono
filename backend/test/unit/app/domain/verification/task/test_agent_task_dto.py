"""The agent task card's wire contract (§12.1 / §20.1, D97).

The commission is shown **before** accept, so the agent knows what the job pays while still
free to decline it. It is a fixed amount per role, so two tasks of the same role on different
tiers must carry the same figure — the property that removes the incentive to prefer a tier.
"""
from types import SimpleNamespace

from main.app.core.state.status import AgentRole, TaskState, VerificationTier
from main.app.domain.verification.task.controller import _agent_task_dto


def _row(role=AgentRole.REGISTRY, tier=VerificationTier.BASIC, commission_minor=None):
    return SimpleNamespace(
        id="task-1", verification_id="v-1", role=role.value, tier=tier.value,
        state=TaskState.ASSIGNED.value, in_pool=False, assignment_mode=None,
        accept_deadline_at=None, remote_bonus_minor=None, submission_payload=None,
        rejection_reason=None, assigned_at=None, accepted_at=None, submitted_at=None,
        commission_minor=commission_minor,
    )


class TestCommissionReachesTheAgent:
    def test_the_card_carries_the_commission_before_accept(self):
        dto = _agent_task_dto(_row(), evidence_count=0, live_commission_minor=2_000_000)
        assert dto.commission_minor == 2_000_000

    def test_the_commission_travels_as_camel_case(self):
        wire = _agent_task_dto(_row(), evidence_count=0, live_commission_minor=2_000_000).model_dump(by_alias=True)
        assert wire["commissionMinor"] == 2_000_000

    def test_the_same_role_on_different_tiers_pays_the_same(self):
        basic = _agent_task_dto(_row(tier=VerificationTier.BASIC), evidence_count=0, live_commission_minor=2_000_000)
        premium = _agent_task_dto(_row(tier=VerificationTier.PREMIUM), evidence_count=0, live_commission_minor=2_000_000)
        assert basic.commission_minor == premium.commission_minor

    def test_an_accepted_task_shows_the_rate_it_locked(self):
        """After accept the card shows what the task will pay — the rate locked then — even if
        the role's live commission has since changed (§12.1 / §20.1)."""
        dto = _agent_task_dto(_row(commission_minor=1_750_000), evidence_count=0, live_commission_minor=2_000_000)
        assert dto.commission_minor == 1_750_000


class TestTheHoldReachesTheAgent:
    """A case being closed (§6.4): the task card says so, so the agent stops before an action fails."""

    def test_a_held_case_is_marked_on_the_card(self):
        wire = _agent_task_dto(_row(), evidence_count=0, live_commission_minor=0, case_on_hold=True).model_dump(by_alias=True)
        assert wire["caseOnHold"] is True

    def test_a_task_is_not_on_hold_by_default(self):
        assert _agent_task_dto(_row(), evidence_count=0, live_commission_minor=0).case_on_hold is False
