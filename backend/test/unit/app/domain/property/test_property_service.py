"""PropertyService (PRD §4.3) — thin first-class property CRUD. Repo mocked, no DB."""
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from unittest.mock import AsyncMock, MagicMock

from main.app.domain.property.models import PropertyInputDto, PropertyType, SellerInfoDto
from main.app.domain.property.service import PropertyService
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import ResourceNotFoundException


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


def _service():
    svc = object.__new__(PropertyService)
    svc._property_repo = MagicMock()
    return svc


def _input(**overrides):
    base = dict(
        property_type=PropertyType.LAND,
        address="12 Admiralty Way, Lekki",
        state="Lagos",
        lga="Eti-Osa",
        seller=SellerInfoDto(name="Ada", phone="+2348012345678"),
        documents=[{"kind": "survey", "url": "s3://x"}],
    )
    base.update(overrides)
    return PropertyInputDto(**base)


class TestCreate:
    async def test_create_persists_customer_and_flattens_seller(self):
        svc = _service()
        svc._property_repo.create_return_model = AsyncMock(return_value=SimpleNamespace(id="prop-1"))

        result = await svc.create("cust-1", _input())

        assert result.id == "prop-1"
        create_dto = svc._property_repo.create_return_model.call_args.args[0]
        assert create_dto.customer_id == "cust-1"
        assert create_dto.property_type == PropertyType.LAND
        # seller DTO is flattened to a plain dict for the JSONB column.
        assert create_dto.seller == {"name": "Ada", "phone": "+2348012345678",
                                     "email": None, "relationship": None, "notes": None}
        assert create_dto.documents == [{"kind": "survey", "url": "s3://x"}]

    async def test_create_allows_null_seller(self):
        svc = _service()
        svc._property_repo.create_return_model = AsyncMock(return_value=SimpleNamespace(id="prop-2"))

        await svc.create("cust-1", _input(seller=None))

        assert svc._property_repo.create_return_model.call_args.args[0].seller is None


class TestUpdate:
    async def test_update_missing_property_raises(self):
        svc = _service()
        svc._property_repo.get_model = AsyncMock(return_value=None)

        with pytest.raises(ResourceNotFoundException):
            await svc.update("nope", _input())
        svc._property_repo.update.assert_not_called() if hasattr(svc._property_repo, "update") else None

    async def test_update_writes_and_returns_reloaded(self):
        svc = _service()
        existing = SimpleNamespace(id="prop-1")
        reloaded = SimpleNamespace(id="prop-1", address="new")
        svc._property_repo.get_model = AsyncMock(side_effect=[existing, reloaded])
        svc._property_repo.update = AsyncMock()

        result = await svc.update("prop-1", _input(address="new"))

        assert result is reloaded
        update_dto = svc._property_repo.update.call_args.args[1]
        assert update_dto.address == "new"
        # property_type is serialised to its enum value on update.
        assert update_dto.property_type == PropertyType.LAND.value


class TestGet:
    async def test_get_returns_existing(self):
        svc = _service()
        row = SimpleNamespace(id="prop-1")
        svc._property_repo.get_model = AsyncMock(return_value=row)

        assert await svc.get("prop-1") is row

    async def test_get_missing_raises(self):
        svc = _service()
        svc._property_repo.get_model = AsyncMock(return_value=None)

        with pytest.raises(ResourceNotFoundException):
            await svc.get("nope")
