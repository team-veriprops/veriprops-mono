"""ReportService — releasing a report is the gate the customer's report sits behind (§8.6, §10.1).

A release creates the next version and supersedes the live one, so a verification never has
two RELEASED reports; the version label says why the version exists (a re-check or tier
upgrade is a new major, an admin revision a minor bump). Reopening a task supersedes the live
report without replacing it, because it no longer describes the case.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.core.state.status import ReportRevisionKind, ReportState
from main.app.domain.audit.models import AuditActionType
from main.app.domain.verification.report.service import ReportService, _next_version_label
from test.utils.db_session import mock_db_session  # noqa: F401  (autouse fixture)


def _service(live=None, latest_version=0):
    """A service whose repo holds *live* as the RELEASED report (or none)."""
    rows = {live.id: live} if live is not None else {}

    async def _create(dto):
        row = SimpleNamespace(id=f"r{dto.report_version}", released_at=None, superseded_at=None, **dto.model_dump())
        rows[row.id] = row
        return row

    async def _update(report_id, dto):
        rows[report_id].state = dto.state

    svc = object.__new__(ReportService)
    svc._report_repo = MagicMock()
    svc._report_repo.get_released = AsyncMock(return_value=live)
    svc._report_repo.latest_version = AsyncMock(return_value=latest_version)
    svc._report_repo.create_return_model = AsyncMock(side_effect=_create)
    svc._report_repo.update = AsyncMock(side_effect=_update)
    svc._report_repo.get_model = AsyncMock(side_effect=lambda report_id: rows[report_id])
    svc._audit = MagicMock()
    return svc


def _live(state=ReportState.RELEASED.value, label="1.0"):
    return SimpleNamespace(id="r1", state=state, version_label=label, released_at=None, superseded_at=None)


async def _release(svc, kind=ReportRevisionKind.INITIAL):
    return await svc.release(
        verification_id="v1", findings={"title": "clean"}, composite_trust_score=82,
        released_by="admin-1", reason="all tasks approved", revision_kind=kind,
    )


class TestRelease:
    async def test_the_first_release_is_version_1_0_and_released_now(self):
        svc = _service()

        report = await _release(svc)

        assert (report.report_version, report.version_label) == (1, "1.0")
        assert report.state == ReportState.RELEASED
        assert report.released_at is not None
        assert (report.composite_trust_score, report.released_by) == (82, "admin-1")
        svc._report_repo.update.assert_not_awaited()

    async def test_a_new_release_supersedes_the_live_report_first(self):
        live = _live()
        svc = _service(live=live, latest_version=1)

        report = await _release(svc, ReportRevisionKind.RECHECK)

        assert live.state == ReportState.SUPERSEDED.value
        assert live.superseded_at is not None
        assert (report.report_version, report.version_label) == (2, "2.0")

    async def test_the_release_is_audited_with_its_version_and_score(self):
        svc = _service()

        report = await _release(svc)

        kwargs = svc._audit.schedule.call_args.kwargs
        assert kwargs["action"] == AuditActionType.REPORT_RELEASED
        assert (kwargs["resource_id"], kwargs["actor_id"]) == (report.id, "admin-1")
        assert kwargs["details"] == {"verification_id": "v1", "version": 1, "trust_score": 82, "reason": "all tasks approved"}


class TestSupersedeCurrent:
    async def test_supersedes_the_live_report_and_audits_the_reopen(self):
        live = _live()
        svc = _service(live=live)

        report = await svc.supersede_current("v1", actor_id="admin-2")

        assert report is live and live.state == ReportState.SUPERSEDED.value
        assert live.superseded_at is not None
        kwargs = svc._audit.schedule.call_args.kwargs
        assert (kwargs["from_state"], kwargs["to_state"]) == (ReportState.RELEASED.value, ReportState.SUPERSEDED.value)
        assert kwargs["details"]["event"] == "superseded_on_reopen"

    async def test_is_a_no_op_without_a_live_report(self):
        svc = _service()

        assert await svc.supersede_current("v1", actor_id="admin-2") is None
        svc._report_repo.update.assert_not_awaited()
        svc._audit.schedule.assert_not_called()


class TestVersionLabel:
    @pytest.mark.parametrize("prior, kind, label", [
        (None, ReportRevisionKind.RECHECK, "1.0"),
        ("2.3", ReportRevisionKind.INITIAL, "1.0"),
        ("1.0", ReportRevisionKind.ADMIN_REVISION, "1.1"),
        ("1.1", ReportRevisionKind.ADMIN_REVISION, "1.2"),
        ("1.2", ReportRevisionKind.RECHECK, "2.0"),
        ("2.0", ReportRevisionKind.TIER_UPGRADE, "3.0"),
        ("garbled", ReportRevisionKind.ADMIN_REVISION, "1.1"),
    ])
    def test_label_follows_the_revision_kind(self, prior, kind, label):
        assert _next_version_label(prior, kind) == label
