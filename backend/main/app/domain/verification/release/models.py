"""Release domain models — S31."""
from __future__ import annotations

from typing import Optional

from main.appodus_utils import Object


class ReleaseDto(Object):
    verification_id: str
    vid: str
    status: str
    completed_at: Optional[str] = None


class FailReleaseDto(Object):
    reason: str


_MIN_FAIL_REASON_LENGTH = 50
