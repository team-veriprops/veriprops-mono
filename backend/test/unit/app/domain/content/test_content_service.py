"""Unit tests for ContentService (S55)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.content.models import (
    ContentItemType,
    CreateContentItemDto,
    ReorderContentItemDto,
    UpdateContentItemDto,
)
from main.app.domain.content.service import ContentService
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import ResourceNotFoundException, ValidationException


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


def _make_row(item_id="item-001", item_type="HOW_IT_WORKS_STEP", published=True):
    row = MagicMock()
    row.id = item_id
    row.item_type = item_type
    row.slug = "test-slug"
    row.title = "Test Title"
    row.body = "Test Body"
    row.meta = None
    row.is_published = published
    row.sort_order = 0
    row.author_id = None
    row.lga = None
    row.state = None
    row.date_created = MagicMock()
    row.date_updated = None
    return row


def _make_svc():
    svc = ContentService.__new__(ContentService)
    repo = MagicMock()
    svc._repo = repo
    return svc, repo


class TestListByType:
    async def test_returns_published_items(self):
        svc, repo = _make_svc()
        row = _make_row()
        repo.list_by_type = AsyncMock(return_value=[row])

        result = await svc.list_by_type(ContentItemType.HOW_IT_WORKS_STEP)

        repo.list_by_type.assert_awaited_once_with(ContentItemType.HOW_IT_WORKS_STEP, True)
        assert len(result) == 1
        assert result[0].title == "Test Title"

    async def test_returns_empty_when_no_items(self):
        svc, repo = _make_svc()
        repo.list_by_type = AsyncMock(return_value=[])

        result = await svc.list_by_type(ContentItemType.FAQ)
        assert result == []


class TestCreateContent:
    async def test_creates_new_item(self):
        svc, repo = _make_svc()
        repo.get_by_slug = AsyncMock(return_value=None)
        new_row = _make_row()
        repo.create = AsyncMock(return_value=MagicMock(data=MagicMock(id="item-001")))
        repo.get_model = AsyncMock(return_value=new_row)

        dto = CreateContentItemDto(
            item_type=ContentItemType.FAQ,
            slug="new-faq-slug",
            title="New FAQ",
            body="Answer here",
        )
        result = await svc.create(dto, "admin-1")

        repo.create.assert_awaited_once()
        assert result.title == "Test Title"

    async def test_raises_on_duplicate_slug(self):
        svc, repo = _make_svc()
        repo.get_by_slug = AsyncMock(return_value=_make_row())

        dto = CreateContentItemDto(
            item_type=ContentItemType.FAQ,
            slug="existing-slug",
            title="New FAQ",
            body="Answer",
        )
        with pytest.raises(ValidationException):
            await svc.create(dto, "admin-1")


class TestPublishContent:
    async def test_publishes_item(self):
        svc, repo = _make_svc()
        row = _make_row(published=False)
        repo.get_model = AsyncMock(side_effect=[row, _make_row(published=True)])
        repo.update = AsyncMock()

        result = await svc.publish("item-001", True, "admin-1")

        repo.update.assert_awaited_once()
        assert result.is_published is True

    async def test_raises_when_not_found(self):
        svc, repo = _make_svc()
        repo.get_model = AsyncMock(return_value=None)

        with pytest.raises(ResourceNotFoundException):
            await svc.publish("nonexistent", True, "admin-1")


class TestDeleteContent:
    async def test_soft_deletes_item(self):
        svc, repo = _make_svc()
        row = _make_row()
        repo.get_model = AsyncMock(return_value=row)

        await svc.delete("item-001", "admin-1")

        assert row.deleted is True

    async def test_raises_when_not_found(self):
        svc, repo = _make_svc()
        repo.get_model = AsyncMock(return_value=None)

        with pytest.raises(ResourceNotFoundException):
            await svc.delete("nonexistent", "admin-1")


class TestReorderContent:
    async def test_sets_sort_order_by_position(self):
        svc, repo = _make_svc()
        row_a = _make_row("a")
        row_b = _make_row("b")
        repo.get_model = AsyncMock(side_effect=[row_a, row_a, row_b, row_b])
        repo.update = AsyncMock()

        await svc.reorder(ReorderContentItemDto(item_ids=["a", "b"]), "admin-1")

        calls = repo.update.call_args_list
        assert calls[0][0][1].sort_order == 0
        assert calls[1][0][1].sort_order == 1


class TestAreaInsights:
    async def test_filters_by_state_and_lga(self):
        svc, repo = _make_svc()
        repo.list_area_insights = AsyncMock(return_value=[])

        await svc.list_area_insights(state="Lagos", lga="Ikeja")

        repo.list_area_insights.assert_awaited_once_with("Lagos", "Ikeja", True)
