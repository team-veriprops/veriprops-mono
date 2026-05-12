"""Re-check repo — S44."""
from __future__ import annotations

from kink import inject

from main.app.domain.verification.recheck.models import (
    RecheckRequest,
    CreateRecheckRequestDto,
    UpdateRecheckRequestDto,
    QueryRecheckRequestDto,
    SearchRecheckRequestDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class RecheckRequestRepo(GenericRepo[
    RecheckRequest,
    CreateRecheckRequestDto,
    UpdateRecheckRequestDto,
    QueryRecheckRequestDto,
    SearchRecheckRequestDto,
]):
    model = RecheckRequest
