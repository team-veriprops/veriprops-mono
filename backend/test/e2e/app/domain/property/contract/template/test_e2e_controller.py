import enum
import unittest

from _pytest.monkeypatch import MonkeyPatch
from starlette import status

from main.app.config.settings import settings
from main.app.domain.property.contract.template.models import UpdateContractTemplateDto, \
    ContractTemplate, SearchContractTemplateDto
from test.e2e.app.domain.property.contract.template.contract_utils import mock_google_drive_client, \
    create_contract_template_dto, create_contract_template
from test.utils.test_utils import get_app_test_client, truncate_entities


class TestContractTemplateController(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.client = get_app_test_client()
        self.client_endpoint = "api/properties/contracts/templates/"

        self.monkeypatch = MonkeyPatch()
        mock_google_drive_client(
            monkeypatch=self.monkeypatch,
            _file_id=settings.GOOGLE_DOC_PARENT_CONTRACT_ID,
            _new_name=create_contract_template_dto.title
        )

    async def asyncTearDown(self):
        self.monkeypatch.undo()
        await self._truncate_tables()
        await self.client.aclose()

    @staticmethod
    async def _truncate_tables():
        await truncate_entities([ContractTemplate])

    async def test_create_contract_template(self):
        response = await self.client.post(self.client_endpoint, json=create_contract_template_dto.model_dump())

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertEqual(response.json()["title"], create_contract_template_dto.title)

    async def test_get_contract_template(self):
        created_contract_template_dto = await create_contract_template(create_contract_template_dto)

        response = await self.client.get(f"{self.client_endpoint}{created_contract_template_dto.id}")

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(response.json()["title"], create_contract_template_dto.title)

    async def test_get_contract_template_page(self):
        await create_contract_template(create_contract_template_dto)

        search_dto = SearchContractTemplateDto(page=0, page_size=10)
        search_params = {
            key: (value.value if isinstance(value, enum.Enum) else value)
            for key, value in search_dto.model_dump(exclude_none=True).items()
        }
        response = await self.client.get(self.client_endpoint, params=search_params)

        print(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual( 1, response.json()["total"])

    async def test_update_contract_template(self):
        created_contract_template_dto = await create_contract_template(create_contract_template_dto)

        update_dto = UpdateContractTemplateDto(
            title="updated title",
            description="Updated description",
        )

        response = await self.client.put(f"{self.client_endpoint}{created_contract_template_dto.id}",
                                         json=update_dto.model_dump())

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(response.json()["title"], update_dto.title)

    async def test_soft_delete_contract_template(self):
        created_contract_template_dto = await create_contract_template(create_contract_template_dto)

        response = await self.client.delete(f"{self.client_endpoint}{created_contract_template_dto.id}")

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(response.json(), True)
