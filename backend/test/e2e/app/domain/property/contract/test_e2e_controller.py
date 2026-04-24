import enum
import unittest

from _pytest.monkeypatch import MonkeyPatch
from starlette import status

from main.app.config.settings import settings
from main.appodus_utils import Utils
from main.app.domain.property.contract.models import UpdatePropertyContractDto, \
    PropertyContract, SearchPropertyContractDto
from main.app.domain.property.contract.template.models import ContractTemplate
from test.e2e.app.domain.property.contract.template.contract_utils import mock_google_drive_client, \
    create_contract_template_dto, create_property_contract_dto, create_property_contract
from test.utils.test_utils import get_app_test_client, truncate_entities


class TestPropertyContractController(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.client = get_app_test_client()
        self.client_endpoint = "api/properties/contracts/"

        self.monkeypatch = MonkeyPatch()
        new_doc_name = Utils.get_contract_title(
            create_contract_template_dto.title,
            create_property_contract_dto.property_id)
        mock_google_drive_client(
            monkeypatch=self.monkeypatch,
            _file_id=settings.GOOGLE_DOC_PARENT_CONTRACT_ID,
            _new_name=new_doc_name,
            _email=create_property_contract_dto.seller_google_email
        )

    async def asyncTearDown(self):
        self.monkeypatch.undo()
        await self._truncate_tables()
        await self.client.aclose()

    @staticmethod
    async def _truncate_tables():
        await truncate_entities([PropertyContract, ContractTemplate])

    async def test_get_property_contract(self):
        created_property_contract_dto = await create_property_contract(create_property_contract_dto)

        response = await self.client.get(f"{self.client_endpoint}{created_property_contract_dto.id}")

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(response.json()["title"], create_property_contract_dto.title)

    async def test_get_seller_property_contract_page(self):
        await create_property_contract(create_property_contract_dto)

        search_dto = SearchPropertyContractDto(page=0, page_size=10)
        search_params = {
            key: (value.value if isinstance(value, enum.Enum) else value)
            for key, value in search_dto.model_dump(exclude_none=True).items()
        }
        response = await self.client.get(self.client_endpoint, params=search_params)

        print(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(response.json()["total"], 1)

    async def test_update_property_contract(self):
        created_property_contract_dto = await create_property_contract(create_property_contract_dto)

        update_dto = UpdatePropertyContractDto(
            title="updated title",
            description="Updated description",
        )

        response = await self.client.put(f"{self.client_endpoint}{created_property_contract_dto.id}",
                                         json=update_dto.model_dump())

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(response.json()["title"], update_dto.title)
