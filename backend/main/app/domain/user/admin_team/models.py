"""Admin team management DTOs — PRD §4.1 (R4.5)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from main.app.domain.user.models import AdminSubRole
from main.appodus_utils import Object


class AdminTeamMemberDto(Object):
    id: str
    email: str
    first_name: str
    last_name: str
    sub_role: AdminSubRole
    created_at: datetime


class ChangeSubRoleRequestDto(Object):
    sub_role: AdminSubRole
