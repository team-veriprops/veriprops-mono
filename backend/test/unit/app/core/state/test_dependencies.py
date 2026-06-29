"""Unit tests for per-tier task composition + dependency config (PRD §4.2, §1.4)."""
import pytest

from main.app.core.state.status import AgentRole, VerificationTier
from main.app.core.state import dependencies as deps

T = VerificationTier
R = AgentRole


# ── Tier composition + required-task counts ──────────────────────────────────

class TestTierComposition:
    def test_basic_roles(self):
        assert deps.roles_for_tier(T.BASIC) == (R.REGISTRY,)

    def test_standard_roles(self):
        assert deps.roles_for_tier(T.STANDARD) == (R.REGISTRY, R.FIELD, R.SURVEYOR)

    def test_premium_roles(self):
        assert deps.roles_for_tier(T.PREMIUM) == (R.REGISTRY, R.FIELD, R.SURVEYOR, R.LAWYER)

    @pytest.mark.parametrize("tier,count", [(T.BASIC, 1), (T.STANDARD, 3), (T.PREMIUM, 4)])
    def test_required_task_count_from_config(self, tier, count):
        assert deps.required_task_count(tier) == count


# ── Lawyer dependency / unlock (§4.2) ────────────────────────────────────────

class TestLawyerDependency:
    def test_premium_lawyer_depends_on_three_siblings(self):
        assert deps.dependencies_for(T.PREMIUM, R.LAWYER) == (R.REGISTRY, R.FIELD, R.SURVEYOR)

    def test_non_lawyer_roles_have_no_dependencies(self):
        for role in (R.REGISTRY, R.FIELD, R.SURVEYOR):
            assert deps.dependencies_for(T.PREMIUM, role) == ()

    def test_standard_has_no_lawyer_dependency(self):
        # Standard has no Lawyer role at all, so no dependency entry.
        assert deps.dependencies_for(T.STANDARD, R.LAWYER) == ()

    def test_lawyer_blocked_until_all_siblings_submitted(self):
        assert deps.is_unlocked(T.PREMIUM, R.LAWYER, []) is False
        assert deps.is_unlocked(T.PREMIUM, R.LAWYER, [R.REGISTRY, R.FIELD]) is False
        assert deps.is_unlocked(T.PREMIUM, R.LAWYER, [R.REGISTRY, R.FIELD, R.SURVEYOR]) is True

    def test_blocking_roles_lists_actual_blockers(self):
        assert deps.blocking_roles(T.PREMIUM, R.LAWYER, [R.REGISTRY]) == (R.FIELD, R.SURVEYOR)
        assert deps.blocking_roles(T.PREMIUM, R.LAWYER, [R.REGISTRY, R.FIELD, R.SURVEYOR]) == ()

    def test_free_role_is_always_unlocked(self):
        assert deps.is_unlocked(T.PREMIUM, R.REGISTRY, []) is True


# ── Acyclicity validation ────────────────────────────────────────────────────

class TestAcyclicity:
    def test_builtin_config_is_acyclic(self):
        # Must not raise (also enforced at import).
        for tier_deps in deps.TASK_DEPENDENCIES.values():
            deps.validate_acyclic(tier_deps)

    def test_direct_cycle_rejected(self):
        cyclic = {R.LAWYER: (R.REGISTRY,), R.REGISTRY: (R.LAWYER,)}
        with pytest.raises(ValueError):
            deps.validate_acyclic(cyclic)

    def test_self_cycle_rejected(self):
        with pytest.raises(ValueError):
            deps.validate_acyclic({R.LAWYER: (R.LAWYER,)})

    def test_transitive_cycle_rejected(self):
        cyclic = {R.FIELD: (R.SURVEYOR,), R.SURVEYOR: (R.REGISTRY,), R.REGISTRY: (R.FIELD,)}
        with pytest.raises(ValueError):
            deps.validate_acyclic(cyclic)
