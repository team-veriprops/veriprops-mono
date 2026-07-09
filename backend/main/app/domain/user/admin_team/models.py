"""Admin team management DTOs (PRD §4.1).

No new table — an admin is a User with ``user_type == ADMIN`` and an ``admin_sub_role``.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from main.app.domain.user.models import AdminSubRole
from main.appodus_utils import Object


class AdminMemberDto(Object):
    id: str
    name: str
    email: str
    sub_role: Optional[AdminSubRole] = None
    active: bool
    date_created: datetime


class ChangeSubRoleDto(Object):
    sub_role: AdminSubRole


class AdminTeamPageDto(Object):
    items: List[AdminMemberDto]
    total: int
    page: int
    page_size: int
