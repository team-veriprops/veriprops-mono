"""ConversationService: ownership and membership of a WhatsApp thread move together (§26.8).

Linking a number gives its thread an owner **and** makes that owner a participant from the
moment of linking; releasing the number takes ownership away and closes the window, leaving
read-only history. Without the participant row the portal list — which is membership-driven —
never showed the customer their own thread.
"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from test.utils.repo_fakes import fake_insert_or_get

from main.app.domain.communication.conversation.models import (
    ConversationChannel,
    ConversationReadOnlyReason,
    ConversationType,
)
from main.app.domain.communication.conversation.service import ConversationService
from main.app.domain.communication.conversation_participant.models import ConversationParticipant
from main.appodus_utils.db.session import db_session_ctx

PHONE = "+2348012345678"
USER_ID = "3f2c0d4e-0000-4000-8000-000000000001"
LINKED_AT = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
RELEASED_AT = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)


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


def _thread(**overrides):
    values = dict(
        id="conv-1", type=ConversationType.GENERAL_SUPPORT.value, verification_id=None,
        subject="WhatsApp enquiry", channel=ConversationChannel.WHATSAPP.value,
        external_ref=PHONE, last_message_at=None, closed=False, created_by=None,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def _service(thread=None, membership=None):
    svc = object.__new__(ConversationService)
    svc._conversation_repo = MagicMock()
    svc._conversation_repo._session = MagicMock()
    svc._conversation_repo.get_whatsapp_thread = AsyncMock(return_value=thread)
    svc._conversation_repo.insert_or_get = fake_insert_or_get(
        lambda values: thread,
        lambda values: _thread(created_by=values["created_by"], external_ref=values["external_ref"]),
    )
    svc._participants = MagicMock()
    svc._participants._session = MagicMock()
    svc._participants.get_for = AsyncMock(return_value=membership)
    created_memberships = []

    def _join(values):
        row = ConversationParticipant(
            conversation_id=values["conversation_id"], user_id=values["user_id"], role=values["role"],
            visible_from=values["visible_from"],
        )
        created_memberships.append(row)
        return row

    # Keyed on the live membership (uq_conv_participants_membership), as the real insert is.
    svc._participants.insert_or_get = fake_insert_or_get(lambda values: membership, _join)
    svc._created_memberships = created_memberships
    return svc


class TestLinkingOpensTheWindow:
    async def test_the_owner_becomes_a_participant_from_the_moment_of_linking(self):
        thread = _thread()
        svc = _service(thread=thread, membership=None)

        await svc.set_whatsapp_thread_owner(PHONE, USER_ID, LINKED_AT)

        assert thread.created_by == USER_ID
        [created] = svc._created_memberships
        assert created.user_id == USER_ID
        assert created.visible_from == LINKED_AT

    async def test_relinking_reopens_an_existing_membership_from_the_new_link(self):
        """A fresh `visible_from`: another account may have held the number in between."""
        membership = ConversationParticipant(
            conversation_id="conv-1", user_id=USER_ID, visible_from=LINKED_AT, visible_until=RELEASED_AT,
        )
        svc = _service(thread=_thread(), membership=membership)
        relinked_at = datetime(2026, 9, 20, 9, 0, tzinfo=timezone.utc)

        await svc.set_whatsapp_thread_owner(PHONE, USER_ID, relinked_at)

        assert svc._created_memberships == []
        assert membership.visible_from == relinked_at
        assert membership.visible_until is None

    async def test_a_number_with_no_thread_yet_is_a_no_op(self):
        svc = _service(thread=None)

        assert await svc.set_whatsapp_thread_owner(PHONE, USER_ID, LINKED_AT) is None
        assert svc._created_memberships == []


class TestReleaseClosesTheWindow:
    async def test_the_thread_loses_its_owner_and_the_history_goes_read_only(self):
        thread = _thread(created_by=USER_ID)
        membership = ConversationParticipant(
            conversation_id="conv-1", user_id=USER_ID, visible_from=LINKED_AT,
        )
        svc = _service(thread=thread, membership=membership)

        await svc.release_whatsapp_thread(PHONE, USER_ID, RELEASED_AT)

        assert thread.created_by is None
        assert membership.visible_until == RELEASED_AT
        assert membership.is_read_only is True

    async def test_releasing_without_a_membership_still_drops_the_owner(self):
        thread = _thread(created_by=USER_ID)
        svc = _service(thread=thread, membership=None)

        await svc.release_whatsapp_thread(PHONE, USER_ID, RELEASED_AT)

        assert thread.created_by is None


class TestAThreadOpenedAfterLinking:
    async def test_a_linked_numbers_first_message_opens_a_thread_its_owner_can_see(self):
        """Linking on the website before ever messaging: the thread only comes into being
        on the first inbound, so it must be created owned and joined, not orphaned."""
        svc = _service(thread=None, membership=None)

        thread = await svc.get_or_create_whatsapp_thread(PHONE, user_id=USER_ID)

        assert thread.created_by == USER_ID
        [created] = svc._created_memberships
        assert created.user_id == USER_ID
        assert created.visible_from is not None

    async def test_an_unlinked_numbers_thread_has_no_participant(self):
        svc = _service(thread=None, membership=None)

        await svc.get_or_create_whatsapp_thread(PHONE)

        assert svc._created_memberships == []


class TestDto:
    def test_a_released_membership_projects_as_read_only(self):
        membership = ConversationParticipant(visible_from=LINKED_AT, visible_until=RELEASED_AT)

        dto = ConversationService.to_dto(_thread(), membership=membership)

        assert dto.read_only is True
        assert dto.read_only_reason == ConversationReadOnlyReason.NUMBER_UNLINKED

    def test_an_open_thread_is_writable_and_keeps_its_channel(self):
        dto = ConversationService.to_dto(_thread())

        assert dto.read_only is False
        assert dto.read_only_reason is None
        assert dto.channel == ConversationChannel.WHATSAPP
        assert dto.external_ref == PHONE


class TestAdminInbox:
    """The console's Conversations list (§16.5) — one page, unread against each admin's own
    read state, and the thread's owner named so a web support thread is not anonymous."""

    ADMIN_ID = "9a1b2c3d-0000-4000-8000-00000000000a"

    async def test_a_page_projects_each_row_with_this_admins_unread_and_the_owner(self):
        from main.app.domain.communication.conversation.repo import AdminInboxRow

        support = _thread(
            id="conv-web", channel=ConversationChannel.WEB.value, external_ref=None,
            subject="General support", last_message_at=RELEASED_AT, created_by=USER_ID,
        )
        read = ConversationParticipant(last_read_at=RELEASED_AT)
        whatsapp = _thread(id="conv-wa", last_message_at=RELEASED_AT)
        svc = _service()
        svc._conversation_repo.list_admin_inbox_page = AsyncMock(return_value=([
            AdminInboxRow(support, None, "Ada Obi", "ada@example.com"),
            AdminInboxRow(whatsapp, read, None, None),
        ], 12))

        page = await svc.list_admin_inbox(self.ADMIN_ID, 1, 2, inbox_filter=None, query="ada")

        svc._conversation_repo.list_admin_inbox_page.assert_awaited_once_with(
            self.ADMIN_ID, 1, 2, inbox_filter=None, query="ada"
        )
        first, second = page.items
        assert (first.unread, first.owner_name, first.owner_email) == (1, "Ada Obi", "ada@example.com")
        assert (second.unread, second.owner_name) == (0, None)
        assert (page.meta.total, page.meta.total_pages, page.meta.page) == (12, 6, 1)

    async def test_the_counter_is_a_single_sql_count(self):
        svc = _service()
        svc._conversation_repo.count_admin_unread = AsyncMock(return_value=4)

        assert await svc.unread_count_for_admin(self.ADMIN_ID) == 4
        svc._conversation_repo.count_admin_unread.assert_awaited_once_with(self.ADMIN_ID)

    async def test_the_unpaged_list_shares_the_inbox_query(self):
        from main.app.domain.communication.conversation.repo import AdminInboxRow

        svc = _service()
        svc._conversation_repo.list_admin_inbox = AsyncMock(return_value=[
            AdminInboxRow(_thread(last_message_at=RELEASED_AT), None, None, None),
        ])

        dtos = await svc.list_for_admin(self.ADMIN_ID)

        assert [d.unread for d in dtos] == [1]
        svc._participants.get_for.assert_not_awaited()  # no per-thread lookups
