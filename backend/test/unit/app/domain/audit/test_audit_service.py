"""Unit tests for AuditLogService read methods — S56 (R19.1, R19.2, R19.3)."""
from __future__ import annotations

import csv
import io
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.audit.models import AuditActionType, AuditEventDto
from main.app.domain.audit.service import AuditLogService
from main.appodus_utils.db.session import db_session_ctx


@pytest.fixture(autouse=True)
def mock_db_session():
    session = MagicMock()
    session.in_transaction.return_value = False

    @asynccontextmanager
    async def _begin():
        yield

    session.begin = _begin
    session.flush = AsyncMock()
    token = db_session_ctx.set(session)
    yield session
    db_session_ctx.reset(token)


def _make_row(
    resource_type="VERIFICATION",
    resource_id="vid-1",
    action=AuditActionType.VERIFICATION_STATE_CHANGED,
    from_state="PAID",
    to_state="IN_PROGRESS",
    actor_id="admin-1",
):
    row = MagicMock()
    row.id = "log-uuid-1"
    row.resource_type = resource_type
    row.resource_id = resource_id
    row.action = action.value
    row.from_state = from_state
    row.to_state = to_state
    row.actor_id = actor_id
    row.ip_address = "1.2.3.4"
    row.meta = {"note": "test"}
    row.occurred_at = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    return row


def _make_svc(list_for_resource=None, list_for_verification_pack=None, list_admin_actions=None):
    repo = MagicMock()
    repo.list_for_resource = list_for_resource or AsyncMock(return_value=([], 0))
    repo.list_for_verification_pack = list_for_verification_pack or AsyncMock(return_value=[])
    repo.list_admin_actions = list_admin_actions or AsyncMock(return_value=([], 0))
    repo.create = AsyncMock()
    return AuditLogService(repo=repo)


class TestGetActivityLog:
    async def test_filters_by_resource_and_strips_actor_id(self):
        row = _make_row()
        svc = _make_svc(list_for_resource=AsyncMock(return_value=([row], 1)))
        result = await svc.get_activity_log("VERIFICATION", "vid-1", page=0, page_size=10)

        assert result.total == 1
        assert len(result.items) == 1
        event: AuditEventDto = result.items[0]
        assert event.action == AuditActionType.VERIFICATION_STATE_CHANGED.value
        assert event.from_state == "PAID"
        assert event.to_state == "IN_PROGRESS"
        # actor_id must NOT appear on AuditEventDto
        assert not hasattr(event, "actor_id") or getattr(event, "actor_id", None) is None

    async def test_empty_result_returns_empty_list(self):
        svc = _make_svc(list_for_resource=AsyncMock(return_value=([], 0)))
        result = await svc.get_activity_log("TASK", "task-1")
        assert result.total == 0
        assert result.items == []

    async def test_pagination_metadata(self):
        rows = [_make_row() for _ in range(3)]
        svc = _make_svc(list_for_resource=AsyncMock(return_value=(rows, 15)))
        result = await svc.get_activity_log("VERIFICATION", "vid-1", page=1, page_size=3)
        assert result.page == 1
        assert result.page_size == 3
        assert result.total == 15


class TestExportVerificationPackCsv:
    async def test_returns_valid_csv_with_expected_columns(self):
        row = _make_row()
        svc = _make_svc(list_for_verification_pack=AsyncMock(return_value=[row]))
        csv_bytes = await svc.export_verification_pack_csv(vid="vid-1", task_ids=["task-1"])

        reader = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8")))
        expected_cols = {
            "occurred_at", "action", "actor_id", "resource_type", "resource_id",
            "from_state", "to_state", "ip_address", "meta",
        }
        assert expected_cols == set(reader.fieldnames)
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["actor_id"] == "admin-1"
        assert rows[0]["action"] == AuditActionType.VERIFICATION_STATE_CHANGED.value

    async def test_empty_pack_returns_headers_only(self):
        svc = _make_svc(list_for_verification_pack=AsyncMock(return_value=[]))
        csv_bytes = await svc.export_verification_pack_csv(vid="vid-1", task_ids=[])
        reader = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8")))
        assert list(reader) == []
        assert reader.fieldnames is not None


class TestListAdminActions:
    async def test_filters_by_action_type_and_paginates(self):
        row = _make_row(action=AuditActionType.ADMIN_CONFIG_CHANGED)
        svc = _make_svc(list_admin_actions=AsyncMock(return_value=([row], 1)))
        result = await svc.list_admin_actions(
            action_types=[AuditActionType.ADMIN_CONFIG_CHANGED.value],
            page=0,
            page_size=10,
        )
        assert result.total == 1
        assert result.items[0].action == AuditActionType.ADMIN_CONFIG_CHANGED.value
        assert result.items[0].actor_id == "admin-1"

    async def test_uses_default_admin_action_types_when_none_provided(self):
        from main.app.domain.audit.service import ADMIN_ACTION_TYPES
        svc = _make_svc()
        await svc.list_admin_actions()
        call_args = svc._repo.list_admin_actions.call_args
        assert call_args.kwargs["action_types"] == ADMIN_ACTION_TYPES

    async def test_empty_result(self):
        svc = _make_svc(list_admin_actions=AsyncMock(return_value=([], 0)))
        result = await svc.list_admin_actions()
        assert result.items == []
        assert result.total == 0
