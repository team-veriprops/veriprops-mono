"""Unit tests for the RBAC permission matrix (R4.4).

Verifies:
- has_permission() correctly maps each AdminSubRole to its allowed permissions.
- Non-admin user_type is always denied.
- Missing or invalid sub_role is always denied.
- Permission enum covers all PRD-required actions.
"""
import pytest

from main.app.domain.user.auth.utils.permissions import Permission, has_permission
from main.app.domain.user.models import AdminSubRole


# ── helpers ───────────────────────────────────────────────────────────────────

def _allow(user_type: str, sub_role: str, permission: Permission) -> bool:
    return has_permission(user_type, sub_role, permission)


ALL_PERMISSIONS = set(Permission)

OPERATIONS_ALLOWED = {
    Permission.APPROVE_AGENT,
    Permission.ASSIGN_AGENT,
    Permission.RESOLVE_DISPUTE,
    Permission.RELEASE_REPORT,
    Permission.VIEW_ADMIN_PANEL,
}

FINANCE_ALLOWED = {
    Permission.APPROVE_PAYOUT,
    Permission.CONFIGURE_PRICING,
    Permission.CONFIRM_WIRE_PAYMENT,
    Permission.VIEW_ADMIN_PANEL,
}


# ── SUPER admin ───────────────────────────────────────────────────────────────

class TestSuperAdmin:
    def test_super_has_all_permissions(self):
        for perm in Permission:
            assert _allow("ADMIN", "SUPER", perm), f"SUPER should have {perm}"

    def test_super_case_insensitive_user_type(self):
        assert _allow("admin", "SUPER", Permission.INVITE_ADMIN)


# ── OPERATIONS admin ──────────────────────────────────────────────────────────

class TestOperationsAdmin:
    @pytest.mark.parametrize("perm", list(OPERATIONS_ALLOWED))
    def test_operations_allowed_permissions(self, perm: Permission):
        assert _allow("ADMIN", "OPERATIONS", perm)

    @pytest.mark.parametrize("perm", list(ALL_PERMISSIONS - OPERATIONS_ALLOWED))
    def test_operations_denied_permissions(self, perm: Permission):
        assert not _allow("ADMIN", "OPERATIONS", perm)


# ── FINANCE admin ─────────────────────────────────────────────────────────────

class TestFinanceAdmin:
    @pytest.mark.parametrize("perm", list(FINANCE_ALLOWED))
    def test_finance_allowed_permissions(self, perm: Permission):
        assert _allow("ADMIN", "FINANCE", perm)

    @pytest.mark.parametrize("perm", list(ALL_PERMISSIONS - FINANCE_ALLOWED))
    def test_finance_denied_permissions(self, perm: Permission):
        assert not _allow("ADMIN", "FINANCE", perm)


# ── Regular user ──────────────────────────────────────────────────────────────

class TestRegularUser:
    @pytest.mark.parametrize("perm", list(Permission))
    def test_user_has_no_permissions(self, perm: Permission):
        assert not _allow("USER", None, perm)

    @pytest.mark.parametrize("perm", list(Permission))
    def test_user_with_sub_role_still_denied(self, perm: Permission):
        assert not _allow("USER", "SUPER", perm)


# ── Edge cases ────────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_none_user_type_denied(self):
        assert not _allow(None, "SUPER", Permission.INVITE_ADMIN)

    def test_none_sub_role_denied(self):
        assert not _allow("ADMIN", None, Permission.INVITE_ADMIN)

    def test_invalid_sub_role_denied(self):
        assert not _allow("ADMIN", "UNKNOWN_ROLE", Permission.APPROVE_AGENT)

    def test_empty_string_user_type_denied(self):
        assert not _allow("", "SUPER", Permission.INVITE_ADMIN)


# ── PRD coverage check ────────────────────────────────────────────────────────

class TestPrdCoverage:
    """Ensure all PRD-required permission actions are present in the enum."""

    def test_invite_admin_exists(self):
        assert Permission.INVITE_ADMIN in Permission

    def test_approve_agent_exists(self):
        assert Permission.APPROVE_AGENT in Permission

    def test_assign_agent_exists(self):
        assert Permission.ASSIGN_AGENT in Permission

    def test_approve_payout_exists(self):
        assert Permission.APPROVE_PAYOUT in Permission

    def test_configure_pricing_exists(self):
        assert Permission.CONFIGURE_PRICING in Permission

    def test_resolve_dispute_exists(self):
        assert Permission.RESOLVE_DISPUTE in Permission

    def test_release_report_exists(self):
        assert Permission.RELEASE_REPORT in Permission
