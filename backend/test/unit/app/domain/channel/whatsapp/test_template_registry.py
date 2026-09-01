"""WhatsAppTemplateService (PRD §7.7, WA-15/WA-41).

The registry exists to answer one operational question honestly: can we actually send
this yet? §7.11 gates launch on it, so the tests that matter are the ones about *not*
being optimistic — a template Meta has never seen, or one whose status we cannot read,
must never read as approved.

Deps mocked, no DB.
"""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.channel.whatsapp.template import service as template_service_module
from main.app.domain.channel.whatsapp.template.models import WhatsAppTemplateStatus
from main.app.domain.channel.whatsapp.template.service import WhatsAppTemplateService
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.integrations.messaging.providers.whatsapp.directory import (
    RemoteTemplate,
    StubTemplateDirectory,
)
from main.appodus_utils.integrations.messaging.templating.whatsapp_templates import (
    declared_templates,
)


@pytest.fixture(autouse=True)
def mock_db_session():
    session = MagicMock()
    session.in_transaction.return_value = False

    @asynccontextmanager
    async def _begin():
        yield

    session.begin = _begin
    session.flush = AsyncMock()
    session.add = MagicMock()
    token = db_session_ctx.set(session)
    yield session
    db_session_ctx.reset(token)


def _service(existing=None):
    svc = object.__new__(WhatsAppTemplateService)
    svc._whatsapp_template_repo = MagicMock()
    rows = {row.name: row for row in (existing or [])}

    async def _get_by_name(name):
        return rows.get(name)

    async def _list_all():
        return list(rows.values())

    async def _create(dto):
        row = SimpleNamespace(
            name=dto.name, category=dto.category, language=dto.language,
            status=dto.status.value, remote_id=dto.remote_id,
            rejection_reason=dto.rejection_reason, last_synced_at=None, deleted=False,
        )
        rows[dto.name] = row
        return row

    def _apply(row, status, remote_id, rejection_reason, at):
        row.status = status.value
        row.remote_id = remote_id
        row.rejection_reason = rejection_reason
        row.last_synced_at = at
        return row

    svc._whatsapp_template_repo.get_by_name = AsyncMock(side_effect=_get_by_name)
    svc._whatsapp_template_repo.list_all = AsyncMock(side_effect=_list_all)
    svc._whatsapp_template_repo.create_return_model = AsyncMock(side_effect=_create)
    svc._whatsapp_template_repo.apply_remote_state = MagicMock(side_effect=_apply)
    svc._whatsapp_template_repo._session = MagicMock()
    return svc, rows


def _directory(templates):
    directory = MagicMock()
    directory.list_templates = AsyncMock(return_value=templates)
    return lambda: directory


def row(name, status=WhatsAppTemplateStatus.NOT_FOUND, reason=None):
    return SimpleNamespace(
        name=name, category="UTILITY", language="en", status=status.value,
        remote_id=None, rejection_reason=reason, last_synced_at=None, deleted=False,
    )


class TestListing:
    async def test_lists_every_declared_template_even_before_a_sync(self):
        # "We have not submitted this yet" is the state the launch gate most needs to
        # show, so the listing is driven by the declarations, not by the table.
        svc, _ = _service()
        registry = await svc.list_all()
        assert [r.name for r in registry] == [d.name for d in declared_templates()]
        assert all(r.status == WhatsAppTemplateStatus.NOT_FOUND for r in registry)

    async def test_carries_the_parameters_so_the_page_is_readable(self):
        svc, _ = _service()
        otp = next(r for r in await svc.list_all() if r.name == "otp_auth")
        assert otp.parameters == ["OTP", "VALIDITY"]
        assert otp.category == "AUTHENTICATION"

    async def test_reflects_a_synced_status(self):
        svc, _ = _service([row("otp_auth", WhatsAppTemplateStatus.APPROVED)])
        otp = next(r for r in await svc.list_all() if r.name == "otp_auth")
        assert otp.status == WhatsAppTemplateStatus.APPROVED


class TestSync(object):
    async def test_creates_a_row_for_every_declared_template(self, monkeypatch):
        svc, rows = _service()
        monkeypatch.setattr(
            template_service_module, "whatsapp_template_directory",
            _directory(await StubTemplateDirectory().list_templates()),
        )
        result = await svc.sync()
        assert result.synced == len(declared_templates())
        assert result.approved == len(declared_templates())
        assert set(rows) == {d.name for d in declared_templates()}

    async def test_a_declared_template_meta_has_never_seen_is_not_found(self, monkeypatch):
        svc, rows = _service()
        monkeypatch.setattr(
            template_service_module, "whatsapp_template_directory", _directory([]),
        )
        result = await svc.sync()
        assert result.missing == len(declared_templates())
        assert all(r.status == WhatsAppTemplateStatus.NOT_FOUND.value for r in rows.values())

    async def test_an_unreadable_status_is_never_read_as_approved(self, monkeypatch):
        # Optimism here would let the §7.11 gate pass on a template that cannot be sent.
        svc, rows = _service()
        monkeypatch.setattr(
            template_service_module, "whatsapp_template_directory",
            _directory([RemoteTemplate(name="otp_auth", status="something_new")]),
        )
        await svc.sync()
        assert rows["otp_auth"].status == WhatsAppTemplateStatus.NOT_FOUND.value

    async def test_carries_a_rejection_reason_through(self, monkeypatch):
        svc, rows = _service()
        monkeypatch.setattr(
            template_service_module, "whatsapp_template_directory",
            _directory([RemoteTemplate(
                name="otp_auth", status="REJECTED", rejection_reason="INVALID_FORMAT",
            )]),
        )
        await svc.sync()
        assert rows["otp_auth"].status == WhatsAppTemplateStatus.REJECTED.value
        assert rows["otp_auth"].rejection_reason == "INVALID_FORMAT"

    async def test_ignores_templates_we_do_not_declare(self, monkeypatch):
        # Somebody else's template on the same business account is not our launch gate.
        svc, rows = _service()
        monkeypatch.setattr(
            template_service_module, "whatsapp_template_directory",
            _directory([RemoteTemplate(name="somebody_elses_promo", status="APPROVED")]),
        )
        await svc.sync()
        assert "somebody_elses_promo" not in rows

    async def test_a_later_sync_clears_a_stale_rejection(self, monkeypatch):
        # The row must be able to move back to approved *and* drop the old reason —
        # the reason the repo mutates the attached row instead of using the update path.
        svc, rows = _service([row("otp_auth", WhatsAppTemplateStatus.REJECTED, "INVALID_FORMAT")])
        monkeypatch.setattr(
            template_service_module, "whatsapp_template_directory",
            _directory([RemoteTemplate(name="otp_auth", status="APPROVED")]),
        )
        await svc.sync()
        assert rows["otp_auth"].status == WhatsAppTemplateStatus.APPROVED.value
        assert rows["otp_auth"].rejection_reason is None


class TestApprovalIsAdvisory:
    async def test_reports_approval_from_the_last_sync(self):
        svc, _ = _service([row("otp_auth", WhatsAppTemplateStatus.APPROVED)])
        assert await svc.is_approved("otp_auth") is True

    async def test_an_unsynced_template_is_not_approved(self):
        svc, _ = _service()
        assert await svc.is_approved("otp_auth") is False


class TestStubDirectory:
    async def test_reports_the_declared_set_without_touching_the_network(self):
        # The determinism contract: CI and e2e run this, and it must never reach Meta.
        templates = await StubTemplateDirectory().list_templates()
        assert {t.name for t in templates} == {d.name for d in declared_templates()}
        assert all(t.status == "APPROVED" for t in templates)
